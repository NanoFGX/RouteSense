"""Travel-time providers.

The planner only talks to the TravelTimeProvider interface, so the estimate below
can be swapped for the Google Routes API (traffic-aware) or OSRM without touching
the planner. The estimate needs no key and no internet, which keeps the demo safe.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from . import config
from .geo import haversine_km

Point = tuple[float, float]


class TravelTimeProvider(Protocol):
    name: str

    def leg(self, a: Point, b: Point, depart_min: float) -> tuple[float, float]:
        """(minutes, km) for one leg leaving at depart_min."""

    def matrix(self, points: list[Point], depart_min: float) -> tuple[list[list[float]], list[list[float]]]:
        """(minutes, km) between every pair of points, leaving at depart_min."""


@dataclass
class EstimateProvider:
    """Distance x detour factor, at a Klang Valley speed that changes by hour."""

    vehicle: str = "motorcycle"
    name: str = "estimate"

    def speed_kmh(self, minute: float) -> float:
        minute = minute % (24 * 60)
        for start, end, speed in config.SPEED_PROFILE_KMH[self.vehicle]:
            if start <= minute < end:
                return speed
        return config.SPEED_PROFILE_KMH[self.vehicle][-1][2]

    def leg(self, a: Point, b: Point, depart_min: float) -> tuple[float, float]:
        km = haversine_km(a, b) * config.DETOUR_FACTOR
        if km < 0.05:
            return 0.0, 0.0
        minutes = km / self.speed_kmh(depart_min) * 60
        return max(minutes, 2.0), km  # parking and walking make no leg shorter than 2 min

    def matrix(self, points: list[Point], depart_min: float) -> tuple[list[list[float]], list[list[float]]]:
        n = len(points)
        minutes = [[0.0] * n for _ in range(n)]
        km = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j:
                    minutes[i][j], km[i][j] = self.leg(points[i], points[j], depart_min)
        return minutes, km


def default_provider(vehicle: str = "motorcycle") -> TravelTimeProvider:
    return EstimateProvider(vehicle=vehicle)
