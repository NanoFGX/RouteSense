"""Demo days in the Klang Valley.

`demo_day()` is the fixed day used in the viva: 16 parcels around Petaling Jaya,
Damansara and Subang Jaya, out of a hub in Section 13. Names, units and phone
numbers are made up. Each stop carries a hidden `profile` (who is home when) that
only the simulator reads; the app never sends it to the phone.

`random_day()` draws fresh days for the experiment.
"""

from __future__ import annotations

import random
import secrets

from . import config
from .risk.synth import sample_customer

HUB = {"label": "RouteSense hub, Section 13, Petaling Jaya", "lat": 3.1106, "lng": 101.6383}
RIDER = {"name": "Hafiz", "vehicle": "motorcycle"}

FULL_DAY = (config.DAY_START, config.DAY_END)

# (id, customer, address, area, lat, lng, property, guardhouse, cod_rm, window, prior failures, hidden profile)
_DEMO = [
    ("s01", "Aisyah", "Block B-12-3, Damansara Jaya condominium", "Damansara Jaya", 3.1288, 101.6168, "high_rise", True, 0, FULL_DAY, 1, "office_worker"),
    ("s02", "Mr. Lim", "Lot 21, Jalan SS21/39 (shop lot)", "Damansara Uptown", 3.1356, 101.6233, "shop_office", False, 0, (600, 1080), 0, "business"),
    ("s03", "Kumar", "No. 14, Jalan SS2/24", "SS2, Petaling Jaya", 3.1180, 101.6214, "landed", False, 85, FULL_DAY, 0, "out_afternoon"),
    ("s04", "Nurul", "No. 7, Lorong Datuk Sulaiman 3", "Taman Tun Dr Ismail", 3.1466, 101.6293, "landed", False, 0, FULL_DAY, 0, "home_most_day"),
    ("s05", "Jason", "Level 8, office tower", "Mutiara Damansara", 3.1570, 101.6106, "shop_office", False, 0, (600, 1080), 0, "business"),
    ("s06", "Mei Ling", "Unit A-15-8, Kota Damansara condominium", "Kota Damansara", 3.1625, 101.5903, "high_rise", True, 120, FULL_DAY, 0, "office_worker"),
    ("s07", "Farid", "No. 3, Jalan BU 11/4 (gated)", "Bandar Utama", 3.1442, 101.6112, "landed", True, 0, FULL_DAY, 0, "home_most_day"),
    ("s08", "Priya", "No. 22, Jalan SS21/56", "Damansara Utama", 3.1338, 101.6198, "landed", False, 0, FULL_DAY, 1, "office_worker"),
    ("s09", "Amir", "Block C-6-2, Kelana Jaya apartment", "Kelana Jaya", 3.1008, 101.6018, "high_rise", True, 0, FULL_DAY, 0, "home_most_day"),
    ("s10", "Siew Ling", "No. 9, Jalan SS7/13", "Kelana Jaya", 3.1048, 101.5968, "landed", False, 45, FULL_DAY, 0, "home_most_day"),
    ("s11", "Daniel", "No. 40, Jalan SS15/4 (shop)", "Subang Jaya", 3.0775, 101.5876, "shop_office", False, 0, (600, 1080), 0, "business"),
    ("s12", "Hana", "Unit 9-3, USJ 1 condominium", "USJ 1", 3.0598, 101.5799, "high_rise", True, 0, FULL_DAY, 0, "out_afternoon"),
    ("s13", "Ravi", "No. 18, Jalan SS17/1F", "Subang Jaya", 3.0822, 101.5932, "landed", False, 0, FULL_DAY, 0, "office_worker"),
    ("s14", "Zainab", "No. 5, Jalan 1/9", "PJ Old Town", 3.0858, 101.6449, "landed", False, 0, FULL_DAY, 0, "home_most_day"),
    ("s15", "Wei Jie", "Tower 2, Sunway serviced apartment", "Bandar Sunway", 3.0732, 101.6069, "high_rise", True, 0, FULL_DAY, 0, "home_most_day"),
    ("s16", "Lina", "No. 11, Jalan 17/29", "Section 17, Petaling Jaya", 3.1268, 101.6376, "landed", False, 60, FULL_DAY, 0, "office_worker"),
]


def _stop(**kw) -> dict:
    return {
        "attempts": 0,
        "status": "pending",
        "reply": None,
        "earliest_min": None,
        "history": [],
        "token": secrets.token_urlsafe(6),
        "phone": None,  # demo: WhatsApp opens the contact picker instead of a real number
        **kw,
    }


def demo_day() -> dict:
    stops = []
    for (sid, cust, addr, area, lat, lng, ptype, guard, cod_rm, tw, prior, profile) in _DEMO:
        stops.append(_stop(
            id=sid, customer=cust, address=addr, area=area, lat=lat, lng=lng, property_type=ptype,
            guardhouse=guard, cod=cod_rm > 0, cod_amount=float(cod_rm), tw_start=tw[0], tw_end=tw[1],
            prior_failures=prior, profile=profile,
        ))
    return {"rider": dict(RIDER), "hub": dict(HUB), "stops": stops}


# Rough box over PJ, Damansara, Subang and Kelana Jaya for random experiment days.
BOX = {"lat": (3.055, 3.165), "lng": (101.580, 101.650)}


def random_day(seed: int, n_stops: int = 15, scenario: str = "mid") -> dict:
    rng = random.Random(seed)
    stops = []
    for i in range(n_stops):
        c = sample_customer(rng, scenario)
        stops.append(_stop(
            id=f"r{i + 1:02d}", customer=f"Customer {i + 1}", address="Synthetic address", area="Klang Valley",
            lat=round(rng.uniform(*BOX["lat"]), 5), lng=round(rng.uniform(*BOX["lng"]), 5), **c,
        ))
    return {"rider": dict(RIDER), "hub": dict(HUB), "stops": stops}
