"""What the risk model is allowed to see: only what a courier would know.

Time of day enters as four slots (morning, midday, afternoon, evening) rather than
a raw hour. Slots give a smooth, explainable risk curve ("evening slot") instead of
one the planner could chase noise in.
"""

from __future__ import annotations

FEATURES = [
    "landed",
    "high_rise",
    "shop_office",
    "guardhouse",
    "cod",
    "cod_amount",
    "prior_failures",
    "slot_morning",
    "slot_midday",
    "slot_afternoon",
    "slot_evening",
    "home_in_office_hours",
    "home_in_evening",
    "shop_outside_hours",
    "window_width_h",
]

SLOTS = (("morning", 0, 12 * 60), ("midday", 12 * 60, 15 * 60), ("afternoon", 15 * 60, 18 * 60), ("evening", 18 * 60, 24 * 60))


def slot_of(minute: float) -> str:
    for name, a, b in SLOTS:
        if a <= minute < b:
            return name
    return "evening"


def featurize(stop: dict, minute: float) -> list[float]:
    ptype = stop["property_type"]
    home = ptype in ("landed", "high_rise")
    slot = slot_of(minute)
    office_hours = 9 * 60 <= minute < 18 * 60
    return [
        float(ptype == "landed"),
        float(ptype == "high_rise"),
        float(ptype == "shop_office"),
        float(bool(stop.get("guardhouse"))),
        float(bool(stop.get("cod"))),
        float(stop.get("cod_amount") or 0.0),
        float(min(int(stop.get("prior_failures", 0)), 3)),
        float(slot == "morning"),
        float(slot == "midday"),
        float(slot == "afternoon"),
        float(slot == "evening"),
        float(home and office_hours),
        float(home and slot == "evening"),
        float(ptype == "shop_office" and not (10 * 60 <= minute < 18 * 60)),
        (stop["tw_end"] - stop["tw_start"]) / 60.0,
    ]
