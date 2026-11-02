"""Load the trained risk model, predict failure risk, explain it in plain words,
and update it with what the customer replied."""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import xgboost as xgb

from .. import config
from ..geo import fmt_time
from .features import FEATURES, featurize, slot_of


def risk_band(p: float) -> str:
    for upper, band in config.RISK_BANDS:
        if p < upper:
            return band
    return "high"


def reply_window(stop: dict) -> tuple[int, int] | None:
    reply = stop.get("reply") or {}
    if reply.get("choice") in ("window", "confirmed"):
        return int(reply.get("after_min") or stop["tw_start"]), int(reply.get("before_min") or stop["tw_end"])
    return None


def apply_reply(p: float, stop: dict, minute: float) -> float:
    """Bayesian-style update: what the customer replied, and any failed attempt
    earlier today, multiply the odds of failure."""
    reply = stop.get("reply") or {}
    failed_today = stop.get("failed_today") or []
    if not reply and not failed_today:
        return p
    p = min(max(p, 1e-4), 1 - 1e-4)
    odds = p / (1 - p)
    residential = stop["property_type"] in ("landed", "high_rise")
    for fm in failed_today:
        if slot_of(fm) == slot_of(minute):
            odds *= config.FAILED_SAME_SLOT_ODDS
        elif residential and 9 * 60 <= fm < 18 * 60 and 9 * 60 <= minute < 18 * 60:
            odds *= config.FAILED_OFFICE_HOURS_ODDS
    window = reply_window(stop)
    if window:
        if window[0] <= minute <= window[1]:
            odds *= config.REPLY_LIKELIHOOD_RATIO["confirmed"]
        else:
            odds *= 4.0  # they told us they will not be home then
    if reply.get("safe_place"):
        odds *= config.REPLY_LIKELIHOOD_RATIO["safe_place"]
    if stop.get("cod") and reply.get("cod_ready"):
        odds *= config.REPLY_LIKELIHOOD_RATIO["cod_ready"]
    return odds / (1 + odds)


class RiskModel:
    def __init__(self) -> None:
        self.booster = xgb.Booster()
        self.booster.load_model(str(config.MODELS_DIR / "risk_xgb.json"))
        self.meta = json.loads((config.MODELS_DIR / "risk_meta.json").read_text())

    def _raw(self, rows: list[list[float]]) -> np.ndarray:
        return self.booster.predict(xgb.DMatrix(np.array(rows, dtype=float), feature_names=FEATURES))

    def base_prob(self, stop: dict, minute: float) -> float:
        return float(self._raw([featurize(stop, minute)])[0])

    def prob(self, stop: dict, minute: float) -> float:
        return apply_reply(self.base_prob(stop, minute), stop, minute)

    def probs_at(self, stop: dict, minutes: list[float]) -> list[float]:
        raw = self._raw([featurize(stop, m) for m in minutes])
        return [apply_reply(float(p), stop, m) for p, m in zip(raw, minutes)]

    def reasons(self, stop: dict, minute: float, k: int = 3) -> list[dict]:
        """Top reasons in plain words, from XGBoost's built-in TreeSHAP contributions."""
        contrib = self.booster.predict(
            xgb.DMatrix(np.array([featurize(stop, minute)]), feature_names=FEATURES), pred_contribs=True
        )[0]
        c = dict(zip(FEATURES, contrib[:-1]))
        groups = {
            "property": c["landed"] + c["high_rise"] + c["shop_office"],
            "guardhouse": c["guardhouse"],
            "cod": c["cod"] + c["cod_amount"],
            "prior": c["prior_failures"],
            "time": sum(c[f] for f in ("slot_morning", "slot_midday", "slot_afternoon", "slot_evening",
                                        "home_in_office_hours", "home_in_evening", "shop_outside_hours")),
            "window": c["window_width_h"],
        }
        ptype = stop["property_type"]
        shop = ptype == "shop_office"
        evening = minute >= 18 * 60
        words_up = {
            "property": {"landed": "Landed house: often no one answers in the day",
                         "high_rise": "High-rise: guardhouse and lift access",
                         "shop_office": "Shop or office: may be closed at this hour"}[ptype],
            "guardhouse": "Guardhouse check-in needed",
            "cod": f"Cash on delivery (RM{stop.get('cod_amount', 0):.0f})",
            "prior": f"Failed at this address before ({stop.get('prior_failures', 0)}x)",
            "time": ("Shop may be closed at this hour" if shop
                     else "Office hours: customer may be at work" if not evening
                     else f"Late slot ({fmt_time(minute)})"),
            "window": "Narrow delivery window",
        }
        words_down = {
            "property": "Property type: usually easy to reach",
            "guardhouse": "No guardhouse",
            "cod": "Prepaid parcel",
            "prior": "No failed attempts here before",
            "time": ("Business hours: shop is open" if shop
                     else "Evening: customers are usually home" if evening
                     else "Good time of day for this stop"),
            "window": "Wide delivery window",
        }
        ranked = sorted(groups.items(), key=lambda kv: -abs(kv[1]))
        out = [{"text": words_up[key] if val > 0 else words_down[key], "effect": "raises" if val > 0 else "lowers"}
               for key, val in ranked if abs(val) > 0.05][:k]

        reply = stop.get("reply") or {}
        window = reply_window(stop)
        if window:
            inside = window[0] <= minute <= window[1]
            text = f"Customer said: home {fmt_time(window[0])} to {fmt_time(window[1])}"
            out.insert(0, {"text": text, "effect": "lowers" if inside else "raises"})
        if reply.get("safe_place"):
            out.insert(0, {"text": "Customer agreed: leave with guard or neighbour", "effect": "lowers"})
        if stop.get("cod") and reply.get("cod_ready"):
            out.insert(0, {"text": "Customer confirmed cash is ready", "effect": "lowers"})
        return out[: k + 2]


@lru_cache(maxsize=1)
def get_model() -> RiskModel:
    return RiskModel()
