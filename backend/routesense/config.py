"""Central settings for RouteSense.

Every number here is an assumption of the prototype. Each one is named so the
FYP report can list it, and so rider interviews or logged outcomes can replace
it later without touching the planner code.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------- paths
BACKEND_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BACKEND_DIR / "models"
DATA_DIR = BACKEND_DIR / "data"
DB_PATH = DATA_DIR / "routesense.db"
FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"

# ---------------------------------------------------------------- the working day
# All times are minutes after midnight, e.g. 9:00 am = 540.
DAY_START = 9 * 60          # rider leaves the hub
DAY_END = 21 * 60           # last delivery must start before 9:00 pm

# ---------------------------------------------------------------- service time
# Minutes spent at the door, by property type (proposal medians, assumption).
SERVICE_MIN = {"landed": 3, "high_rise": 10, "shop_office": 6}
COD_EXTRA_MIN = 2           # counting cash
FLAT_SERVICE_MIN = 3        # what a generic route app assumes for every stop
FAILED_ATTEMPT_MIN = 6      # ringing, calling the customer, waiting, then leaving

# ---------------------------------------------------------------- failure-aware planning
# Expected minutes lost when an attempt fails: the wasted trip, the call, and the
# parcel riding again tomorrow. Turns a risk difference into a planning cost.
FAIL_COST_MIN = 45
# A stop's "good window" holds the hours whose risk is within this margin of its lowest.
GOOD_WINDOW_MARGIN = 0.05
# Below this risk difference the planner leaves the stop's timing alone.
MIN_RISK_GAIN = 0.08
# A good window shorter than this is treated as noise, not a real pattern.
MIN_GOOD_WINDOW_MIN = 60
# Cost units per travel minute inside the solver (lets fractional penalties stay integers).
COST_PER_MIN = 100
# Cost of every minute the working day lasts (0.1 travel-minute): keeps the day
# from stretching into the evening unless the risk saving pays for it.
SPAN_COST_PER_MIN = 10
# Small pull toward doing each stop early when timing does not change its risk
# (0.02 travel-minute per minute), so the evening wave holds only what needs it.
EARLY_PREF_PER_MIN = 2

RETRY_GAP_MIN = 90          # earliest same-day retry after a failed attempt
MAX_ATTEMPTS_PER_DAY = 2
# Retry the same day only if some later slot is predicted below this risk;
# otherwise carry the parcel to tomorrow and ask the customer for a time.
RETRY_MAX_RISK = 0.35
# A failed attempt today is evidence about that slot (odds multipliers).
FAILED_SAME_SLOT_ODDS = 4.0
FAILED_OFFICE_HOURS_ODDS = 2.5

# Risk bands shown to the rider.
RISK_BANDS = ((0.15, "low"), (0.35, "medium"), (1.01, "high"))

# How a customer's reply changes the odds that the attempt fails (likelihood
# ratios, assumption until logged outcomes can estimate them).
REPLY_LIKELIHOOD_RATIO = {
    "confirmed": 0.15,      # "I'll be home" for the planned time
    "safe_place": 0.20,     # "leave it with the guard / a neighbour"
    "cod_ready": 0.55,      # "cash is ready" (COD parcels only)
}

# ---------------------------------------------------------------- travel-time estimate
# Used until a Google Routes API key is set. Straight-line distance times a detour
# factor, at a Klang Valley speed that changes through the day (assumption).
DETOUR_FACTOR = 1.35
SPEED_PROFILE_KMH = {
    "motorcycle": [
        (0, 7 * 60, 35), (7 * 60, 9 * 60 + 30, 22), (9 * 60 + 30, 16 * 60 + 30, 30),
        (16 * 60 + 30, 19 * 60 + 30, 20), (19 * 60 + 30, 24 * 60, 32),
    ],
    "car": [
        (0, 7 * 60, 40), (7 * 60, 9 * 60 + 30, 15), (9 * 60 + 30, 16 * 60 + 30, 25),
        (16 * 60 + 30, 19 * 60 + 30, 14), (19 * 60 + 30, 24 * 60, 32),
    ],
}

# ---------------------------------------------------------------- simulation
# Real legs run slower than planned: a pessimistic factor plus seeded noise.
SIM_TRAVEL_FACTOR = 1.10
SIM_TRAVEL_NOISE_SIGMA = 0.15
SIM_SERVICE_NOISE_SIGMA = 0.20
DEFAULT_REPLY_RATE = 0.6
