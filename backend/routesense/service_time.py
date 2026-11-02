"""Minutes spent at each stop."""

from __future__ import annotations

from . import config


def service_minutes(stop: dict, mode: str = "lookup") -> float:
    """'lookup' = RouteSense (by property type); 'flat' = what generic route apps assume."""
    if mode == "flat":
        return float(config.FLAT_SERVICE_MIN)
    minutes = float(config.SERVICE_MIN.get(stop["property_type"], config.FLAT_SERVICE_MIN))
    if stop.get("cod"):
        minutes += config.COD_EXTRA_MIN
    return minutes
