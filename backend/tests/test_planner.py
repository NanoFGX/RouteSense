from routesense import config
from routesense.demo_day import demo_day
from routesense.planner import make_plan, retry_decision
from routesense.risk.model import get_model
from routesense.service_time import service_minutes
from routesense.travel import default_provider

HUB = (demo_day()["hub"]["lat"], demo_day()["hub"]["lng"])


def _plan(strategy, stops):
    return make_plan(strategy, stops, HUB, config.DAY_START, default_provider(), get_model(), time_limit_ms=400)


def test_every_stop_is_planned_inside_its_window():
    stops = demo_day()["stops"]
    for strategy in ("nearest", "time_optimal", "routesense"):
        plan = _plan(strategy, stops)
        assert len(plan.stops) + len(plan.dropped) == len(stops)
        by_id = {s["id"]: s for s in stops}
        for p in plan.stops:
            s = by_id[p.stop_id]
            mode = "lookup" if strategy == "routesense" else "flat"
            assert s["tw_start"] <= p.start_min + 1e-6
            assert p.start_min + service_minutes(s, mode) <= s["tw_end"] + 1, (strategy, s["customer"])


def test_shops_are_served_before_closing():
    plan = _plan("routesense", demo_day()["stops"])
    shops = {s["id"] for s in demo_day()["stops"] if s["property_type"] == "shop_office"}
    for p in plan.stops:
        if p.stop_id in shops:
            assert p.leave_min <= 18 * 60


def test_customer_reply_window_is_respected():
    stops = demo_day()["stops"]
    aisyah = next(s for s in stops if s["customer"] == "Aisyah")
    aisyah["reply"] = {"choice": "window", "after_min": 18 * 60 + 30}
    plan = _plan("routesense", stops)
    p = next(p for p in plan.stops if p.stop_id == aisyah["id"])
    assert p.start_min >= 18 * 60 + 30


def test_routesense_expects_fewer_failures_than_a_normal_app():
    stops = demo_day()["stops"]
    assert _plan("routesense", stops).expected_failures < _plan("time_optimal", stops).expected_failures


def test_no_retry_after_two_attempts():
    stop = dict(demo_day()["stops"][0], attempts=2)
    assert retry_decision(stop, 12 * 60, get_model())["retry"] is False
