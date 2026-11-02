"""Replay a delivery day under a planning strategy.

The plan is made from what the rider knows. What actually happens comes from
the hidden ground truth (risk/synth.py): legs run a little slower than planned,
and each attempt fails with the true probability for that customer at that time.

Strategies (experiment labels in brackets):
  nearest             the rider's usual way, no retries                 (S0)
  time_optimal        a typical route app, no retries                   (S1)
  routesense          failure-aware plan, same-day retries, re-plans    (S2)
  routesense_replies  as above, after customers reply to the link       (S3)
"""

from __future__ import annotations

import copy
import random
import statistics

from . import config
from .planner import STRATEGIES, make_plan, retry_decision, stop_window
from .risk.model import RiskModel, get_model
from .risk.synth import failure_reason, true_fail_prob
from .service_time import service_minutes
from .travel import TravelTimeProvider, default_provider

ADAPTIVE = ("routesense", "routesense_replies")


def simulated_reply(stop: dict, rng: random.Random) -> dict:
    """What this customer would answer, given who they really are."""
    profile = stop["profile"]
    if profile == "office_worker":
        reply = {"choice": "window", "after_min": 18 * 60 + 30, "before_min": None}
    elif profile == "out_afternoon":
        reply = {"choice": "window", "after_min": None, "before_min": 13 * 60 + 30}
    elif profile == "business":
        reply = {"choice": "window", "after_min": 10 * 60, "before_min": 18 * 60}
    else:
        reply = {"choice": "confirmed", "after_min": None, "before_min": None}
    if stop["property_type"] == "high_rise" and stop.get("guardhouse") and rng.random() < 0.5:
        reply["safe_place"] = True
    if stop.get("cod") and rng.random() < 0.9:
        reply["cod_ready"] = True
    reply["source"] = "simulated"
    return reply


def apply_simulated_replies(stops: list[dict], rng: random.Random, reply_rate: float) -> int:
    count = 0
    for s in stops:
        if rng.random() < reply_rate:
            s["reply"] = simulated_reply(s, rng)
            count += 1
    return count


def simulate_day(
    day: dict,
    strategy: str,
    seed: int,
    reply_rate: float = config.DEFAULT_REPLY_RATE,
    travel: TravelTimeProvider | None = None,
    model: RiskModel | None = None,
    time_limit_ms: int = 250,
) -> dict:
    travel = travel or default_provider(day.get("rider", {}).get("vehicle", "motorcycle"))
    model = model or get_model()
    rng = random.Random(seed)
    reply_rng = random.Random(seed * 7919 + 13)

    stops = copy.deepcopy(day["stops"])
    for s in stops:
        s.update(reply=None, attempts=0, status="pending", earliest_min=None, failed_today=[])
    replies = apply_simulated_replies(stops, reply_rng, reply_rate) if strategy == "routesense_replies" else 0
    by_id = {s["id"]: s for s in stops}

    hub = (day["hub"]["lat"], day["hub"]["lng"])
    pos, t = hub, float(config.DAY_START)
    plan = make_plan(strategy, stops, pos, t, travel, model, time_limit_ms)
    first_plan = plan.to_dict()
    queue = [p.stop_id for p in plan.stops]
    carried = set(plan.dropped)

    events, km_total, unpaid, waited, active, late = [], 0.0, 0.0, 0.0, 0.0, 0
    delivered = first_try = failed_attempts = replans = 0

    while queue:
        sid = queue.pop(0)
        s = by_id[sid]
        mins, km = travel.leg(pos, (s["lat"], s["lng"]), t)
        actual = mins * config.SIM_TRAVEL_FACTOR * rng.lognormvariate(0, config.SIM_TRAVEL_NOISE_SIGMA)
        arrival = t + actual
        lo, hi = stop_window(s, config.DAY_START)
        start = max(arrival, lo)
        waited += start - arrival
        km_total += km
        s["attempts"] += 1
        failed = rng.random() < true_fail_prob(s, start)
        pos = (s["lat"], s["lng"])

        if failed:
            dur = config.FAILED_ATTEMPT_MIN * rng.lognormvariate(0, config.SIM_SERVICE_NOISE_SIGMA)
            unpaid += actual + dur
            active += actual + dur
            failed_attempts += 1
            reason = failure_reason(s, start, rng)
            t = start + dur
            s["failed_today"].append(start)
            retry = strategy in ADAPTIVE and retry_decision(s, t, model)["retry"]
            events.append({"t": round(start), "stop_id": sid, "customer": s["customer"], "event": "failed",
                           "reason": reason, "attempt": s["attempts"], "retry": retry})
            if retry:
                s["earliest_min"] = t + config.RETRY_GAP_MIN
            else:
                s["status"] = "carried"
                carried.add(sid)
            if strategy in ADAPTIVE:
                remaining = [by_id[q] for q in queue] + ([s] if retry else [])
                plan = make_plan(strategy, remaining, pos, t, travel, model, time_limit_ms)
                queue = [p.stop_id for p in plan.stops]
                carried |= set(plan.dropped)
                replans += 1
        else:
            dur = service_minutes(s, "lookup") * rng.lognormvariate(0, config.SIM_SERVICE_NOISE_SIGMA)
            active += actual + dur
            delivered += 1
            first_try += s["attempts"] == 1
            late += start > hi
            s["status"] = "delivered"
            t = start + dur
            events.append({"t": round(start), "stop_id": sid, "customer": s["customer"], "event": "delivered",
                           "attempt": s["attempts"]})

        if t > config.DAY_END + 60:
            carried |= set(queue)
            break

    n = len(stops)
    hours = max((t - config.DAY_START) / 60, 0.1)
    active_hours = max(active / 60, 0.1)
    return {
        "strategy": strategy,
        "label": STRATEGIES[strategy],
        "seed": seed,
        "parcels": n,
        "delivered": delivered,
        "delivered_first_try": first_try,
        "first_try_rate": round(first_try / n, 3),
        "failed_attempts": failed_attempts,
        "carried_over": n - delivered,
        "unpaid_min": round(unpaid, 1),
        "km": round(km_total, 1),
        "finish_min": round(t, 1),
        "work_hours": round(hours, 2),
        "active_min": round(active, 1),
        "parcels_per_active_hour": round(delivered / active_hours, 2),
        "late_stops": late,
        "free_min": round(waited, 1),
        "replans": replans,
        "replies": replies,
        "events": events,
        "first_plan": first_plan,
    }


METRIC_KEYS = ("delivered", "delivered_first_try", "first_try_rate", "failed_attempts", "carried_over",
               "unpaid_min", "km", "finish_min", "work_hours", "active_min", "parcels_per_active_hour", "free_min")


def compare(day: dict, strategies=tuple(STRATEGIES), replays: int = 8, seed: int = 1,
            reply_rate: float = config.DEFAULT_REPLY_RATE) -> dict:
    """Run every strategy on the same day and the same random draws, and average."""
    model = get_model()
    travel = default_provider(day.get("rider", {}).get("vehicle", "motorcycle"))
    out = {}
    for strat in strategies:
        runs = [simulate_day(day, strat, seed + r, reply_rate, travel, model) for r in range(replays)]
        summary = {k: round(statistics.mean(run[k] for run in runs), 2) for k in METRIC_KEYS}
        out[strat] = {"label": STRATEGIES[strat], "replays": replays, "mean": summary,
                      "per_replay_first_try": [run["delivered_first_try"] for run in runs],
                      "example": {k: v for k, v in runs[0].items() if k != "first_plan"}}
    return {"reply_rate": reply_rate, "replays": replays, "strategies": out}
