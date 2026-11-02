"""Synthetic ground truth: who is home, and when.

Every customer has a hidden availability profile. The learned risk model never
sees it; it only sees what a courier would know (property type, guardhouse, COD,
time of day, past failures). The simulator draws outcomes from this truth, so the
model is always judged against something it did not produce.

All shares and probabilities below are assumptions of the prototype, chosen so
the three scenarios land near the proposal's 15 / 25 / 40 % failure mixes. Rider
interviews and logged outcomes are how they get replaced.
"""

from __future__ import annotations

import math
import random

from .. import config

# Hours a profile is usually reachable at the door, and how reliably.
PROFILES = {
    "office_worker": {"home": [(18 * 60 + 30, 23 * 60)], "presence": 0.92},
    "home_most_day": {"home": [(8 * 60, 22 * 60 + 30)], "presence": 0.93},
    "out_afternoon": {"home": [(8 * 60, 13 * 60 + 30)], "presence": 0.90},
    "business": {"home": [(10 * 60, 18 * 60)], "presence": 0.95},
}
SOMEONE_ELSE_HOME = 0.10  # family member or helper answers outside the profile's hours

PROPERTY_SHARE = {"landed": 0.45, "high_rise": 0.40, "shop_office": 0.15}
GUARDHOUSE_SHARE = {"landed": 0.15, "high_rise": 0.85, "shop_office": 0.0}
COD_SHARE = 0.20  # about 20% of Malaysian orders (Mordor Intelligence, via the FYP A dossier)

# Profile mix per property type, per scenario.
PROFILE_MIX = {
    "low": {
        "landed": {"office_worker": 0.03, "home_most_day": 0.93, "out_afternoon": 0.04},
        "high_rise": {"office_worker": 0.06, "home_most_day": 0.88, "out_afternoon": 0.06},
        "shop_office": {"business": 0.98, "home_most_day": 0.02},
    },
    "mid": {
        "landed": {"office_worker": 0.16, "home_most_day": 0.74, "out_afternoon": 0.10},
        "high_rise": {"office_worker": 0.24, "home_most_day": 0.64, "out_afternoon": 0.12},
        "shop_office": {"business": 0.95, "home_most_day": 0.05},
    },
    "high": {
        "landed": {"office_worker": 0.40, "home_most_day": 0.42, "out_afternoon": 0.18},
        "high_rise": {"office_worker": 0.50, "home_most_day": 0.32, "out_afternoon": 0.18},
        "shop_office": {"business": 0.90, "home_most_day": 0.10},
    },
}
SCENARIO_TARGET = {"low": 0.15, "mid": 0.25, "high": 0.40}

# How likely an address already has failed attempts on record, by profile.
PRIOR_FAILURE_RATE = {"office_worker": 0.35, "out_afternoon": 0.25, "home_most_day": 0.08, "business": 0.05}


def _pick(rng: random.Random, shares: dict[str, float]) -> str:
    r, acc = rng.random(), 0.0
    for key, share in shares.items():
        acc += share
        if r < acc:
            return key
    return key


def presence_prob(profile: str, minute: float) -> float:
    spec = PROFILES[profile]
    inside = any(a <= minute < b for a, b in spec["home"])
    return spec["presence"] if inside else SOMEONE_ELSE_HOME


def true_fail_prob(stop: dict, minute: float) -> float:
    """Ground-truth chance that an attempt at `minute` fails, given the hidden profile
    and whatever the customer told us (reply)."""
    reply = stop.get("reply") or {}
    safe_place = bool(reply.get("safe_place"))
    cod_ready = (not stop.get("cod")) or bool(reply.get("cod_ready"))

    p_home = presence_prob(stop["profile"], minute)

    fail_if_home = 0.03 + 0.03 * min(int(stop.get("prior_failures", 0)), 2)
    if stop["property_type"] == "high_rise" and stop.get("guardhouse") and not safe_place:
        fail_if_home += 0.05   # guard holds the rider, no lift access, unit hard to find
    if not cod_ready:
        fail_if_home += 0.08   # cash not ready

    fail_if_away = 0.12 if safe_place else 0.88
    p = p_home * fail_if_home + (1 - p_home) * fail_if_away
    return min(max(p, 0.01), 0.97)


def failure_reason(stop: dict, minute: float, rng: random.Random) -> str:
    """Plausible reason for a failed attempt, consistent with the ground truth."""
    reply = stop.get("reply") or {}
    away = rng.random() > presence_prob(stop["profile"], minute)
    if away and not reply.get("safe_place"):
        return "Customer not home"
    if stop.get("cod") and not reply.get("cod_ready") and rng.random() < 0.6:
        return "COD cash not ready"
    if stop["property_type"] == "high_rise" and stop.get("guardhouse"):
        return "Stopped at guardhouse"
    return "No answer"


def sample_customer(rng: random.Random, scenario: str = "mid", property_type: str | None = None) -> dict:
    """One synthetic delivery: observable fields plus the hidden profile."""
    ptype = property_type or _pick(rng, PROPERTY_SHARE)
    profile = _pick(rng, PROFILE_MIX[scenario][ptype])
    cod = rng.random() < COD_SHARE
    cod_amount = round(min(400.0, max(15.0, rng.lognormvariate(math.log(60), 0.6))), 0) if cod else 0.0
    prior = 0
    if rng.random() < PRIOR_FAILURE_RATE[profile]:
        prior = 1 if rng.random() < 0.75 else 2
    if profile == "business":
        tw = (10 * 60, 18 * 60)
    elif rng.random() < 0.15:
        start = rng.choice([9, 10, 12, 14, 16, 18]) * 60
        tw = (start, min(start + rng.choice([2, 3, 4]) * 60, config.DAY_END))
    else:
        tw = (config.DAY_START, config.DAY_END)
    return {
        "property_type": ptype,
        "guardhouse": rng.random() < GUARDHOUSE_SHARE[ptype],
        "cod": cod,
        "cod_amount": cod_amount,
        "prior_failures": prior,
        "tw_start": tw[0],
        "tw_end": tw[1],
        "profile": profile,
    }


def sample_attempt_minute(rng: random.Random, tw: tuple[int, int]) -> int:
    """When couriers historically arrive: mostly daytime, some evening runs."""
    lo, hi = tw
    for _ in range(20):
        if rng.random() < 0.78:
            minute = rng.uniform(9 * 60 + 15, 18 * 60)
        else:
            minute = rng.uniform(18 * 60, 21 * 60)
        if lo <= minute <= hi:
            return int(minute)
    return int(rng.uniform(lo, hi))


def generate_attempts(n_routes: int = 340, stops_per_route: int = 15, scenario: str = "mid", seed: int = 42) -> list[dict]:
    """Historical-style attempt log: one row per attempt, grouped by route for the split."""
    rng = random.Random(seed)
    rows = []
    for route in range(n_routes):
        for _ in range(stops_per_route):
            c = sample_customer(rng, scenario)
            minute = sample_attempt_minute(rng, (c["tw_start"], c["tw_end"]))
            p = true_fail_prob(c, minute)
            rows.append({**c, "route_id": route, "minute": minute, "true_p": p, "failed": int(rng.random() < p)})
    return rows
