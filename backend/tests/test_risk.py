from routesense.demo_day import demo_day
from routesense.risk.model import get_model, risk_band


def _stop(name):
    return next(s for s in demo_day()["stops"] if s["customer"] == name)


def test_probabilities_are_valid():
    m = get_model()
    for s in demo_day()["stops"]:
        for minute in (9 * 60, 13 * 60, 19 * 60):
            p = m.prob(s, minute)
            assert 0 < p < 1


def test_customer_reply_lowers_risk():
    m = get_model()
    s = _stop("Aisyah")
    before = m.prob(s, 19 * 60)
    s["reply"] = {"choice": "window", "after_min": 18 * 60 + 30}
    assert m.prob(s, 19 * 60) < before
    assert m.prob(s, 10 * 60) > m.prob(s, 19 * 60)  # outside the stated window it rises


def test_safe_place_and_cash_ready_lower_risk():
    m = get_model()
    s = _stop("Mei Ling")
    before = m.prob(s, 11 * 60)
    s["reply"] = {"choice": "confirmed", "safe_place": True, "cod_ready": True}
    assert m.prob(s, 11 * 60) < before


def test_a_failed_attempt_raises_risk_in_that_slot():
    m = get_model()
    s = _stop("Ravi")
    before = m.prob(s, 11 * 60)
    s["failed_today"] = [10 * 60 + 30]
    assert m.prob(s, 11 * 60) > before


def test_reasons_are_given_in_plain_words():
    m = get_model()
    reasons = m.reasons(_stop("Priya"), 11 * 60)
    assert reasons and all(r["effect"] in ("raises", "lowers") and r["text"] for r in reasons)


def test_bands():
    assert risk_band(0.05) == "low" and risk_band(0.2) == "medium" and risk_band(0.5) == "high"
