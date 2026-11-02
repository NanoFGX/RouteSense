"""RouteSense API.

    uvicorn routesense.api:app --reload --port 8000      (from the backend folder)
    Interactive docs: http://localhost:8000/docs

The rider app and the customer reply page both talk to these endpoints. When the
frontend has been built (frontend/dist), this server also serves it, so the whole
prototype runs from one address.
"""

from __future__ import annotations

import os
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import date
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, store
from .demo_day import demo_day
from .geo import fmt_time
from .planner import STRATEGIES, make_plan, retry_decision
from .risk.model import get_model, risk_band
from .service_time import service_minutes
from .simulator import compare, simulate_day
from .travel import default_provider

@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_model()
    _start_compare((8, 1, config.DEFAULT_REPLY_RATE))  # warm the Compare screen in the background
    yield


app = FastAPI(
    lifespan=lifespan,
    title="RouteSense API",
    version="0.3.0",
    description="Failure-aware delivery planning for Malaysian parcel riders (FYP prototype).",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

OPEN = ("pending", "retry")
_lock = threading.Lock()


# ------------------------------------------------------------------ day state helpers
def _new_day() -> dict:
    day = demo_day()
    hub = day["hub"]
    day.update(
        id=uuid.uuid4().hex[:12],
        date=date.today().isoformat(),
        clock_min=config.DAY_START,
        position={"lat": hub["lat"], "lng": hub["lng"], "label": hub["label"]},
        plan=None,
        plan_version=0,
        events=[{"t": config.DAY_START, "text": "Day loaded: 16 parcels from the Section 13 hub"}],
    )
    for s in day["stops"]:
        s["failed_today"] = []
    return day


def _get_day() -> dict:
    day = store.load_day()
    if day is None:
        day = _new_day()
        store.save_day(day)
    return day


def _find(day: dict, stop_id: str) -> dict:
    for s in day["stops"]:
        if s["id"] == stop_id:
            return s
    raise HTTPException(404, f"No stop {stop_id}")


def _event(day: dict, text: str, stop_id: str | None = None, kind: str = "info") -> None:
    day["events"].append({"t": round(day["clock_min"]), "text": text, "stop_id": stop_id, "kind": kind})


def _planned(day: dict) -> dict[str, dict]:
    return {p["stop_id"]: p for p in (day.get("plan") or {}).get("stops", [])}


def _replan(day: dict, why: str | None = None) -> None:
    model = get_model()
    travel = default_provider(day["rider"]["vehicle"])
    before = {k: v["start_min"] for k, v in _planned(day).items()}
    open_stops = [s for s in day["stops"] if s["status"] in OPEN]
    pos = (day["position"]["lat"], day["position"]["lng"])
    plan = make_plan("routesense", open_stops, pos, day["clock_min"], travel, model, time_limit_ms=1500).to_dict()
    for p in plan["stops"]:
        old = before.get(p["stop_id"])
        p["moved_min"] = round(p["start_min"] - old) if old is not None else None
    for sid in plan["dropped"]:
        s = _find(day, sid)
        s["status"] = "carried"
        _event(day, f"{s['customer']}: no time left today, carried to tomorrow", sid, "warn")
    day["plan_version"] += 1
    plan["version"] = day["plan_version"]
    plan["made_at_min"] = day["clock_min"]
    day["plan"] = plan
    if why:
        _event(day, f"Plan v{day['plan_version']}: {why}", kind="plan")


def _public_stop(day: dict, s: dict, planned: dict[str, dict]) -> dict:
    model = get_model()
    p = planned.get(s["id"])
    minute = p["start_min"] if p else day["clock_min"]
    risk = model.prob(s, minute) if s["status"] in OPEN else None
    out = {k: v for k, v in s.items() if k not in ("profile", "failed_today")}
    out.update(
        service_min=service_minutes(s),
        risk=round(risk, 3) if risk is not None else None,
        risk_band=risk_band(risk) if risk is not None else None,
        risk_at_min=minute,
        reasons=model.reasons(s, minute) if risk is not None else [],
        planned=p,
        failed_attempts_today=len(s.get("failed_today") or []),
    )
    return out


def _public_day(day: dict) -> dict:
    planned = _planned(day)
    order = {p["stop_id"]: i for i, p in enumerate((day.get("plan") or {}).get("stops", []))}
    stops = sorted(day["stops"], key=lambda s: (s["status"] not in OPEN, order.get(s["id"], 999), s["id"]))
    public = [_public_stop(day, s, planned) for s in stops]
    next_stop = next((s["id"] for s in public if s["status"] in OPEN and s["planned"]), None)
    counts = {k: sum(1 for s in day["stops"] if s["status"] == k)
              for k in ("pending", "retry", "delivered", "carried", "self_collect")}
    return {
        "id": day["id"], "date": day["date"], "rider": day["rider"], "hub": day["hub"],
        "clock_min": day["clock_min"], "clock_label": fmt_time(day["clock_min"]), "position": day["position"],
        "plan": {k: v for k, v in day["plan"].items() if k != "stops"} if day.get("plan") else None,
        "stops": public, "next_stop_id": next_stop, "counts": counts,
        "events": day["events"][-40:], "public_base_url": os.environ.get("ROUTESENSE_PUBLIC_URL"),
        "day_start": config.DAY_START, "day_end": config.DAY_END,
    }


# ------------------------------------------------------------------ rider endpoints
@app.get("/api/health")
def health() -> dict:
    meta = get_model().meta
    return {"ok": True, "model_trained_at": meta["trained_at"], "travel_times": default_provider().name}


@app.get("/api/day")
def get_day() -> dict:
    with _lock:
        return _public_day(_get_day())


@app.post("/api/day/reset")
def reset_day() -> dict:
    with _lock:
        day = _new_day()
        store.save_day(day)
        return _public_day(day)


@app.post("/api/plan")
def plan_day() -> dict:
    with _lock:
        day = _get_day()
        _replan(day, "planned from " + day["position"]["label"].split(",")[0])
        store.save_day(day)
        return _public_day(day)


@app.get("/api/plan/preview")
def preview_plan(strategy: Literal["nearest", "time_optimal", "routesense"] = "time_optimal") -> dict:
    """What another planner would do with the same open stops. Nothing is saved."""
    day = _get_day()
    open_stops = [s for s in day["stops"] if s["status"] in OPEN]
    pos = (day["position"]["lat"], day["position"]["lng"])
    model = get_model()
    plan = make_plan(strategy, open_stops, pos, day["clock_min"], default_provider(day["rider"]["vehicle"]), model)
    return {"strategy": strategy, "label": STRATEGIES[strategy], **plan.to_dict()}


class OutcomeIn(BaseModel):
    stop_id: str
    status: Literal["delivered", "failed"]
    reason: str | None = None


@app.post("/api/outcome")
def record_outcome(body: OutcomeIn) -> dict:
    with _lock:
        day = _get_day()
        s = _find(day, body.stop_id)
        if s["status"] not in OPEN:
            raise HTTPException(400, f"{s['customer']} is already {s['status']}")
        p = _planned(day).get(s["id"])
        start = max(day["clock_min"], p["start_min"] if p else day["clock_min"])
        s["attempts"] += 1
        day["position"] = {"lat": s["lat"], "lng": s["lng"], "label": s["area"]}
        if body.status == "delivered":
            s["status"] = "delivered"
            s["delivered_min"] = start
            day["clock_min"] = start + service_minutes(s)
            msg = f"Delivered to {s['customer']} at {fmt_time(start)}"
            _event(day, msg, s["id"], "good")
        else:
            reason = body.reason or "Customer not home"
            s.setdefault("failed_today", []).append(start)
            s["history"].append({"t": start, "reason": reason})
            day["clock_min"] = start + config.FAILED_ATTEMPT_MIN
            decision = retry_decision(s, day["clock_min"], get_model())
            if decision["retry"]:
                s["status"] = "retry"
                s["earliest_min"] = decision["earliest_min"]
                msg = f"{s['customer']}: {reason.lower()}. Retry planned, best around {fmt_time(decision['best_min'])}"
            else:
                s["status"] = "carried"
                msg = f"{s['customer']}: {reason.lower()}. {decision['why']}: carried to tomorrow, ask for a time"
            _event(day, msg, s["id"], "bad")
        store.log_outcome(day["id"], s, body.status, body.reason, start)
        if any(x["status"] in OPEN for x in day["stops"]):
            _replan(day, "after " + s["customer"] + (" was delivered" if body.status == "delivered" else "'s failed attempt"))
        else:
            day["plan"] = None
        store.save_day(day)
        return {"message": msg, "day": _public_day(day)}


@app.get("/api/stops/{stop_id}/risk")
def stop_risk(stop_id: str) -> dict:
    """Failure risk across the day, for the 'best time' chart on the Next stop screen."""
    day = _get_day()
    s = _find(day, stop_id)
    model = get_model()
    grid = list(range(config.DAY_START, config.DAY_END + 1, 30))
    risks = model.probs_at(s, grid)
    return {"stop_id": stop_id, "points": [{"minute": m, "label": fmt_time(m), "risk": round(r, 3)}
                                            for m, r in zip(grid, risks)]}


# ------------------------------------------------------------------ customer reply link
class ReplyIn(BaseModel):
    choice: Literal["confirmed", "window", "tomorrow", "self_collect"]
    after_min: int | None = None
    before_min: int | None = None
    safe_place: bool = False
    cod_ready: bool = False


def _by_token(day: dict, token: str) -> dict:
    for s in day["stops"]:
        if s["token"] == token:
            return s
    raise HTTPException(404, "This link has expired or is not valid.")


@app.get("/api/reply/{token}")
def reply_view(token: str) -> dict:
    day = _get_day()
    s = _by_token(day, token)
    p = _planned(day).get(s["id"])
    eta = None
    if p:
        eta = {"from": fmt_time(max(p["start_min"] - 30, config.DAY_START)), "to": fmt_time(p["start_min"] + 30)}
    return {
        "customer": s["customer"], "rider": day["rider"]["name"], "area": s["area"], "status": s["status"],
        "cod": s["cod"], "cod_amount": s["cod_amount"], "property_type": s["property_type"],
        "guardhouse": s["guardhouse"], "eta": eta, "reply": s.get("reply"), "date": day["date"],
        "window": {"from": fmt_time(s["tw_start"]), "to": fmt_time(s["tw_end"])},
    }


@app.post("/api/reply/{token}")
def reply_submit(token: str, body: ReplyIn) -> dict:
    with _lock:
        day = _get_day()
        s = _by_token(day, token)
        if s["status"] not in OPEN:
            raise HTTPException(400, "This parcel is no longer on today's route.")
        if body.choice == "tomorrow":
            s["status"] = "carried"
            s["reply"] = {"choice": "tomorrow"}
            summary = "asked for tomorrow"
        elif body.choice == "self_collect":
            s["status"] = "self_collect"
            s["reply"] = {"choice": "self_collect"}
            summary = "will pick it up at a self-collect point"
        else:
            s["reply"] = body.model_dump()
            s["reply"]["source"] = "customer link"
            parts = []
            if body.choice == "window":
                if body.after_min:
                    parts.append(f"home after {fmt_time(body.after_min)}")
                if body.before_min:
                    parts.append(f"home before {fmt_time(body.before_min)}")
            else:
                parts.append("home today")
            if body.safe_place:
                parts.append("leave with guard or neighbour")
            if body.cod_ready and s["cod"]:
                parts.append("cash ready")
            summary = ", ".join(parts)
        _event(day, f"{s['customer']} replied: {summary}", s["id"], "reply")
        if day.get("plan") and any(x["status"] in OPEN for x in day["stops"]):
            _replan(day, f"after {s['customer']}'s reply")
        store.save_day(day)
        p = _planned(day).get(s["id"])
        if s["status"] == "carried":
            message = f"Thanks, {s['customer']}. {day['rider']['name']} will bring it tomorrow."
        elif s["status"] == "self_collect":
            message = f"Thanks, {s['customer']}. Your parcel will wait at the nearest self-collect point."
        elif p:
            message = (f"Thanks, {s['customer']}. {day['rider']['name']} now plans to arrive around "
                       f"{fmt_time(p['start_min'])}.")
        else:
            message = f"Thanks, {s['customer']}. Your rider has your answer."
        return {"ok": True, "message": message}


# ------------------------------------------------------------------ evidence: simulation and comparison
class SimulateIn(BaseModel):
    strategy: Literal["nearest", "time_optimal", "routesense", "routesense_replies"] = "routesense_replies"
    seed: int = 1
    reply_rate: float = config.DEFAULT_REPLY_RATE


@app.post("/api/simulate")
def simulate(body: SimulateIn) -> dict:
    """Replay the demo day with one strategy. Outcomes come from the hidden ground truth."""
    base = demo_day()
    result = simulate_day(base, body.strategy, body.seed, body.reply_rate)
    coords = {s["id"]: {"lat": s["lat"], "lng": s["lng"], "customer": s["customer"], "area": s["area"]}
              for s in base["stops"]}
    return {**result, "stops": coords, "hub": base["hub"]}


_compare_cache: dict[tuple, dict] = {}
_compare_running: set[tuple] = set()


def _run_compare(key: tuple) -> None:
    replays, seed, rate = key
    try:
        _compare_cache[key] = compare(demo_day(), replays=replays, seed=seed, reply_rate=rate)
    finally:
        _compare_running.discard(key)


@app.get("/api/compare")
def get_compare(replays: int = Query(8, ge=1, le=30), seed: int = 1,
                reply_rate: float = Query(config.DEFAULT_REPLY_RATE, ge=0, le=1)) -> dict:
    """All four strategies on the demo day, same random draws, averaged over replays.
    Takes about 30 seconds the first time; then it is cached."""
    key = (replays, seed, round(reply_rate, 2))
    if key in _compare_cache:
        return {"status": "ready", **_compare_cache[key]}
    _start_compare(key)
    return {"status": "computing"}


def _start_compare(key: tuple) -> None:
    if key in _compare_cache or key in _compare_running:
        return
    _compare_running.add(key)
    threading.Thread(target=_run_compare, args=(key,), daemon=True).start()


@app.get("/api/model")
def model_info() -> dict:
    return {**get_model().meta, "logged_outcomes": store.outcome_count(),
            "retrain_threshold": 300, "strategies": STRATEGIES}


# ------------------------------------------------------------------ the built app (one address for everything)
if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        candidate = config.FRONTEND_DIST / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(config.FRONTEND_DIST / "index.html")
