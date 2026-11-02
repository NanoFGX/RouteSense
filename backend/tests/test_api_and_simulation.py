import statistics

from fastapi.testclient import TestClient

from routesense.api import app
from routesense.demo_day import demo_day
from routesense.simulator import simulate_day


def test_rider_and_customer_flow():
    with TestClient(app) as c:
        day = c.post("/api/day/reset").json()
        assert len(day["stops"]) == 16 and day["plan"] is None
        assert all("profile" not in s for s in day["stops"])  # ground truth never leaves the server

        day = c.post("/api/plan").json()
        assert day["plan"]["version"] == 1 and day["next_stop_id"]

        aisyah = next(s for s in day["stops"] if s["customer"] == "Aisyah")
        view = c.get(f"/api/reply/{aisyah['token']}").json()
        assert view["rider"] == "Hafiz"
        r = c.post(f"/api/reply/{aisyah['token']}", json={"choice": "window", "after_min": 1110})
        assert r.status_code == 200 and "6:30 pm" in r.json()["message"]

        day = c.get("/api/day").json()
        aisyah = next(s for s in day["stops"] if s["customer"] == "Aisyah")
        assert aisyah["planned"]["start_min"] >= 1110 and day["plan"]["version"] == 2

        first = day["next_stop_id"]
        r = c.post("/api/outcome", json={"stop_id": first, "status": "failed", "reason": "Customer not home"})
        assert r.status_code == 200
        assert r.json()["day"]["counts"]["retry"] + r.json()["day"]["counts"]["carried"] == 1

        assert c.get("/api/reply/not-a-token").status_code == 404


def test_simulation_bookkeeping():
    r = simulate_day(demo_day(), "time_optimal", seed=5)
    assert r["delivered"] + r["carried_over"] == r["parcels"]
    assert r["delivered_first_try"] <= r["delivered"]


def test_replies_reduce_failed_trips_on_the_demo_day():
    seeds = range(1, 7)
    app_fail = statistics.mean(simulate_day(demo_day(), "time_optimal", s)["failed_attempts"] for s in seeds)
    rs_fail = statistics.mean(simulate_day(demo_day(), "routesense_replies", s)["failed_attempts"] for s in seeds)
    assert rs_fail < app_fail
