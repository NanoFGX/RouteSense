"""Route planners.

routesense    OR-Tools with time windows, service time by property type, and
              risk-weighted soft windows: each stop is pulled toward the hours
              when it is least likely to fail. (S2 and S3 in the experiment.)
time_optimal  The same solver as a generic route app: traffic times and time
              windows, a flat service time, no failure risk. (S1)
nearest       The rider's usual way: always ride to the nearest next stop. (S0)

All three return the same Plan shape, so the app and the simulator can compare them.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from . import config
from .risk.model import RiskModel, risk_band
from .service_time import service_minutes
from .travel import TravelTimeProvider

DROP_PENALTY = 10_000_000  # dropping a stop (carry it to tomorrow) is a last resort


@dataclass
class PlannedStop:
    stop_id: str
    arrival_min: float
    start_min: float
    leave_min: float
    wait_min: float
    travel_min: float
    km: float
    risk: float
    risk_band: str
    good_window: list[int] | None = None
    retry: bool = False


@dataclass
class Plan:
    strategy: str
    stops: list[PlannedStop]
    dropped: list[str]
    start_min: float
    finish_min: float
    total_km: float
    total_travel_min: float
    expected_failures: float
    solve_ms: int
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def stop_window(stop: dict, start_min: float, service_min: float = 0.0) -> tuple[int, int]:
    """Hard window for starting service: the parcel's window, the customer's stated
    window, the earliest retry time and the end of the day. Service must finish
    before the window closes (a shop shuts at 6 pm, not at 6 pm plus ten minutes)."""
    lo, hi = stop["tw_start"], stop["tw_end"]
    reply = stop.get("reply") or {}
    if reply.get("choice") in ("window", "confirmed"):
        lo = max(lo, int(reply.get("after_min") or lo))
        hi = min(hi, int(reply.get("before_min") or hi))
    lo = max(lo, int(stop.get("earliest_min") or 0), int(start_min))
    hi = min(hi - service_min, config.DAY_END)
    return int(lo), int(hi)


def good_window(stop: dict, lo: int, hi: int, model: RiskModel) -> tuple[list[int] | None, int]:
    """Hours (within the hard window) when this stop is least likely to fail, and the
    per-minute penalty for planning it outside them."""
    if hi - lo < 30:
        return None, 0
    grid = list(range(lo, hi + 1, 30))
    risks = model.probs_at(stop, grid)
    best = min(range(len(grid)), key=lambda i: risks[i])
    limit = risks[best] + config.GOOD_WINDOW_MARGIN
    a = b = best
    while a > 0 and risks[a - 1] <= limit:
        a -= 1
    while b < len(grid) - 1 and risks[b + 1] <= limit:
        b += 1
    outside = [r for i, r in enumerate(risks) if i < a or i > b]
    if not outside or (min(grid[b] + 30, hi) - grid[a]) < config.MIN_GOOD_WINDOW_MIN:
        return None, 0
    gain = sum(outside) / len(outside) - risks[best]
    if gain < config.MIN_RISK_GAIN:
        return None, 0
    coeff = round(config.COST_PER_MIN * config.FAIL_COST_MIN * gain / 60)
    return [grid[a], min(grid[b] + 30, hi)], max(coeff, 1)


def _timeline(order: list[int], stops: list[dict], minutes, km, service, windows, start_min, cumul=None):
    """Walk the chosen order and compute arrival, wait, service start and departure."""
    out, t, prev = [], float(start_min), 0
    for node in order:
        k = node - 1
        travel = minutes[prev][node]
        arrival = t + travel
        start = max(arrival, windows[k][0])
        if cumul is not None:
            start = max(start, float(cumul[node]))
        leave = start + service[node]
        out.append((k, arrival, start, leave, start - arrival, travel, km[prev][node]))
        t, prev = leave, node
    return out


def _finish(strategy, stops, timeline, dropped_idx, start_min, model, windows_good, solve_ms, notes):
    planned = []
    for k, arrival, start, leave, wait, travel, dist in timeline:
        s = stops[k]
        p = model.prob(s, start) if model else 0.0
        planned.append(PlannedStop(
            stop_id=s["id"], arrival_min=round(arrival, 1), start_min=round(start, 1), leave_min=round(leave, 1),
            wait_min=round(wait, 1), travel_min=round(travel, 1), km=round(dist, 2), risk=round(p, 3),
            risk_band=risk_band(p), good_window=windows_good.get(k), retry=bool(s.get("attempts", 0)),
        ))
    finish = planned[-1].leave_min if planned else start_min
    return Plan(
        strategy=strategy, stops=planned, dropped=[stops[k]["id"] for k in dropped_idx], start_min=start_min,
        finish_min=finish, total_km=round(sum(p.km for p in planned), 2),
        total_travel_min=round(sum(p.travel_min for p in planned), 1),
        expected_failures=round(sum(p.risk for p in planned), 2), solve_ms=solve_ms, notes=notes,
    )


def plan_route(
    stops: list[dict],
    start_pos: tuple[float, float],
    start_min: float,
    travel: TravelTimeProvider,
    model: RiskModel | None,
    *,
    use_risk: bool = True,
    service_mode: str = "lookup",
    time_limit_ms: int = 1500,
    strategy: str = "routesense",
) -> Plan:
    t0 = time.perf_counter()
    if not stops:
        return Plan(strategy, [], [], start_min, start_min, 0.0, 0.0, 0.0, 0)

    n = len(stops)
    points = [start_pos] + [(s["lat"], s["lng"]) for s in stops]
    mat_min, mat_km = travel.matrix(points, start_min)
    # open route: node n+1 is a free end, so the rider does not have to ride back to the hub
    minutes = [row + [0.0] for row in mat_min] + [[0.0] * (n + 2)]
    km = [row + [0.0] for row in mat_km] + [[0.0] * (n + 2)]
    service = [0.0] + [service_minutes(s, service_mode) for s in stops] + [0.0]
    windows = [stop_window(s, start_min, service[k + 1]) for k, s in enumerate(stops)]

    manager = pywrapcp.RoutingIndexManager(n + 2, 1, [0], [n + 1])
    routing = pywrapcp.RoutingModel(manager)

    def time_cb(i, j):
        a, b = manager.IndexToNode(i), manager.IndexToNode(j)
        return int(round(minutes[a][b] + service[a]))

    def cost_cb(i, j):
        a, b = manager.IndexToNode(i), manager.IndexToNode(j)
        return int(round(minutes[a][b] * config.COST_PER_MIN))

    time_idx = routing.RegisterTransitCallback(time_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(routing.RegisterTransitCallback(cost_cb))
    routing.AddDimension(time_idx, 24 * 60, 24 * 60 + 600, False, "time")
    tdim = routing.GetDimensionOrDie("time")
    tdim.CumulVar(routing.Start(0)).SetRange(int(start_min), int(start_min))
    tdim.SetSpanCostCoefficientForAllVehicles(config.SPAN_COST_PER_MIN)

    notes, goods, infeasible = [], {}, []
    for k, s in enumerate(stops):
        idx = manager.NodeToIndex(k + 1)
        lo, hi = windows[k]
        if lo > hi:
            infeasible.append(k)
            routing.AddDisjunction([idx], 0)
            continue
        tdim.CumulVar(idx).SetRange(lo, hi)
        routing.AddDisjunction([idx], DROP_PENALTY)
        gw, coeff = good_window(s, lo, hi, model) if (use_risk and model is not None) else (None, 0)
        if gw:
            goods[k] = gw
            tdim.SetCumulVarSoftLowerBound(idx, gw[0], coeff)
            tdim.SetCumulVarSoftUpperBound(idx, gw[1], coeff)
        else:
            tdim.SetCumulVarSoftUpperBound(idx, lo, config.EARLY_PREF_PER_MIN)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.FromMilliseconds(time_limit_ms)
    solution = routing.SolveWithParameters(params)

    if solution is None:
        notes.append("Solver found no plan in time; fell back to nearest next stop.")
        return plan_nearest(stops, start_pos, start_min, travel, model, service_mode=service_mode, strategy=strategy, notes=notes)

    order, cumul, idx = [], {}, routing.Start(0)
    while not routing.IsEnd(idx):
        node = manager.IndexToNode(idx)
        if 1 <= node <= n:
            order.append(node)
            cumul[node] = solution.Value(tdim.CumulVar(idx))
        idx = solution.Value(routing.NextVar(idx))
    visited = {node - 1 for node in order}
    dropped = [k for k in range(n) if k not in visited]
    timeline = _timeline(order, stops, minutes, km, service, windows, start_min, cumul)
    ms = int((time.perf_counter() - t0) * 1000)
    return _finish(strategy, stops, timeline, dropped, start_min, model, goods, ms, notes)


def plan_nearest(
    stops: list[dict],
    start_pos: tuple[float, float],
    start_min: float,
    travel: TravelTimeProvider,
    model: RiskModel | None,
    *,
    service_mode: str = "flat",
    strategy: str = "nearest",
    notes: list[str] | None = None,
) -> Plan:
    """Greedy: ride to the closest stop that can still be reached inside its window."""
    t0 = time.perf_counter()
    remaining = list(range(len(stops)))
    windows = [stop_window(s, start_min, service_minutes(s, service_mode)) for s in stops]
    pos, t = start_pos, float(start_min)
    timeline = []
    while remaining:
        best = None
        for k in remaining:
            lo, hi = windows[k]
            mins, dist = travel.leg(pos, (stops[k]["lat"], stops[k]["lng"]), t)
            if lo <= hi and t + mins <= hi and (best is None or mins < best[1]):
                best = (k, mins, dist)
        if best is None:
            break
        k, mins, dist = best
        arrival = t + mins
        start = max(arrival, windows[k][0])
        leave = start + service_minutes(stops[k], service_mode)
        timeline.append((k, arrival, start, leave, start - arrival, mins, dist))
        remaining.remove(k)
        pos, t = (stops[k]["lat"], stops[k]["lng"]), leave
    ms = int((time.perf_counter() - t0) * 1000)
    return _finish(strategy, stops, timeline, remaining, start_min, model, {}, ms, notes or [])


def retry_decision(stop: dict, now_min: float, model: RiskModel) -> dict:
    """After a failed attempt: retry later today only if a clearly safer slot remains."""
    if stop.get("attempts", 0) >= config.MAX_ATTEMPTS_PER_DAY:
        return {"retry": False, "why": "Already tried twice today"}
    earliest = now_min + config.RETRY_GAP_MIN
    probe = {**stop, "earliest_min": earliest}
    lo, hi = stop_window(probe, now_min, service_minutes(stop))
    if lo > hi:
        return {"retry": False, "why": "No time left in its window today"}
    grid = list(range(lo, hi + 1, 30))
    risks = model.probs_at(stop, grid)
    best = min(range(len(grid)), key=lambda i: risks[i])
    if risks[best] > config.RETRY_MAX_RISK:
        return {"retry": False, "why": "No safer time left today", "best_risk": round(risks[best], 2)}
    return {"retry": True, "earliest_min": earliest, "best_min": grid[best], "best_risk": round(risks[best], 2)}


STRATEGIES = {
    "nearest": "Rider's usual way (nearest next stop)",
    "time_optimal": "Typical route app (shortest time)",
    "routesense": "RouteSense",
    "routesense_replies": "RouteSense with customer replies",
}


def make_plan(strategy: str, stops, start_pos, start_min, travel, model, time_limit_ms: int = 1500) -> Plan:
    if strategy == "nearest":
        return plan_nearest(stops, start_pos, start_min, travel, model)
    if strategy == "time_optimal":
        return plan_route(stops, start_pos, start_min, travel, model, use_risk=False, service_mode="flat",
                          time_limit_ms=time_limit_ms, strategy="time_optimal")
    return plan_route(stops, start_pos, start_min, travel, model, use_risk=True, service_mode="lookup",
                      time_limit_ms=time_limit_ms, strategy=strategy)
