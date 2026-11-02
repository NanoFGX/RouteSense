"""Train the delivery-failure risk model.

    python -m routesense.risk.train            # trains on the 'mid' (25 %) scenario

Steps (CRISP-DM: data understanding, preparation, modelling, evaluation):
1. Generate seeded synthetic attempts for the 15 / 25 / 40 % scenarios.
2. Run the three data checks from the proposal: grounded, plausible, sensitive.
3. Split by route (no route appears in both train and test).
4. Compare logistic regression (baseline) against XGBoost.
5. Save the XGBoost model and a metrics file the app shows on its Model screen.

No class weights: the planner turns probabilities into minutes of expected loss,
so it needs calibrated probabilities. Imbalance at 15-40 % failures is mild;
recall on failures is reported at the 'high' band threshold instead.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import numpy as np
import xgboost as xgb
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .. import config
from .features import FEATURES, featurize
from .synth import SCENARIO_TARGET, generate_attempts

HIGH_BAND = 0.35


def to_xy(rows: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    X = np.array([featurize(r, r["minute"]) for r in rows], dtype=float)
    y = np.array([r["failed"] for r in rows], dtype=int)
    groups = np.array([r["route_id"] for r in rows])
    return X, y, groups


def evaluate(y: np.ndarray, p: np.ndarray) -> dict:
    pred = (p >= HIGH_BAND).astype(int)
    return {
        "pr_auc": round(float(average_precision_score(y, p)), 3),
        "roc_auc": round(float(roc_auc_score(y, p)), 3),
        "brier": round(float(brier_score_loss(y, p)), 4),
        "recall_high_band": round(float(recall_score(y, pred)), 3),
        "precision_high_band": round(float(precision_score(y, pred, zero_division=0)), 3),
        "mean_predicted": round(float(p.mean()), 3),
        "observed_rate": round(float(y.mean()), 3),
    }


def rate(rows: list[dict], cond) -> float:
    sub = [r for r in rows if cond(r)]
    return round(sum(r["failed"] for r in sub) / max(len(sub), 1), 3)


def data_checks(by_scenario: dict[str, list[dict]]) -> dict:
    mid = by_scenario["mid"]
    cod_share = sum(r["cod"] for r in mid) / len(mid)
    grounded = {
        "cod_share": round(cod_share, 3),
        "cod_share_target": 0.20,
        "failure_rate_by_scenario": {k: rate(v, lambda r: True) for k, v in by_scenario.items()},
        "failure_rate_targets": SCENARIO_TARGET,
    }
    grounded["passed"] = abs(cod_share - 0.20) < 0.03 and all(
        abs(grounded["failure_rate_by_scenario"][k] - SCENARIO_TARGET[k]) < 0.04 for k in SCENARIO_TARGET
    )
    plausible = {
        "landed_office_hours": rate(mid, lambda r: r["property_type"] == "landed" and 9 * 60 <= r["minute"] < 18 * 60),
        "landed_evening": rate(mid, lambda r: r["property_type"] == "landed" and r["minute"] >= 18 * 60),
        "high_rise": rate(mid, lambda r: r["property_type"] == "high_rise"),
        "landed": rate(mid, lambda r: r["property_type"] == "landed"),
        "cod": rate(mid, lambda r: r["cod"]),
        "no_cod": rate(mid, lambda r: not r["cod"]),
        "prior_failure": rate(mid, lambda r: r["prior_failures"] > 0),
        "no_prior_failure": rate(mid, lambda r: r["prior_failures"] == 0),
    }
    plausible["passed"] = (
        plausible["landed_office_hours"] > plausible["landed_evening"]
        and plausible["high_rise"] > plausible["landed"]
        and plausible["cod"] > plausible["no_cod"]
        and plausible["prior_failure"] > plausible["no_prior_failure"]
    )
    return {"grounded": grounded, "plausible": plausible}


def fit_models(rows: list[dict], seed: int) -> tuple[dict, xgb.XGBClassifier]:
    X, y, groups = to_xy(rows)
    split = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
    train_idx, test_idx = next(split.split(X, y, groups))
    Xtr, Xte, ytr, yte = X[train_idx], X[test_idx], y[train_idx], y[test_idx]

    lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
    lr.fit(Xtr, ytr)
    p_lr = lr.predict_proba(Xte)[:, 1]

    xgbm = xgb.XGBClassifier(
        n_estimators=200, max_depth=3, learning_rate=0.05, subsample=0.9, colsample_bytree=0.9,
        min_child_weight=10, reg_lambda=5.0, eval_metric="logloss", random_state=seed,
    )
    xgbm.fit(Xtr, ytr)
    p_xgb = xgbm.predict_proba(Xte)[:, 1]

    metrics = {
        "train_rows": int(len(train_idx)),
        "test_rows": int(len(test_idx)),
        "test_routes": int(len(set(groups[test_idx]))),
        "logistic_regression": evaluate(yte, p_lr),
        "xgboost": evaluate(yte, p_xgb),
    }
    return metrics, xgbm


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the RouteSense failure-risk model")
    parser.add_argument("--scenario", default="mid", choices=["low", "mid", "high"])
    parser.add_argument("--routes", type=int, default=340, help="routes of 15 stops (340 x 15 = 5,100 attempts)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    by_scenario = {sc: generate_attempts(args.routes, 15, sc, args.seed) for sc in ("low", "mid", "high")}
    checks = data_checks(by_scenario)

    sensitivity = {}
    for sc, rows in by_scenario.items():
        m, _ = fit_models(rows, args.seed)
        sensitivity[sc] = {"failure_rate": m["xgboost"]["observed_rate"], "xgb_pr_auc": m["xgboost"]["pr_auc"],
                           "lr_pr_auc": m["logistic_regression"]["pr_auc"]}
    checks["sensitive"] = {
        "by_scenario": sensitivity,
        "passed": sensitivity["low"]["failure_rate"] < sensitivity["mid"]["failure_rate"] < sensitivity["high"]["failure_rate"]
        and all(v["xgb_pr_auc"] > v["failure_rate"] for v in sensitivity.values()),
    }

    metrics, model = fit_models(by_scenario[args.scenario], args.seed)
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model.get_booster().save_model(str(config.MODELS_DIR / "risk_xgb.json"))
    meta = {
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scenario": args.scenario,
        "seed": args.seed,
        "features": FEATURES,
        "high_band_threshold": HIGH_BAND,
        "metrics": metrics,
        "data_checks": checks,
        "note": "Synthetic, seeded data. No class weights, so probabilities stay calibrated for planning.",
    }
    (config.MODELS_DIR / "risk_meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps({"metrics": metrics, "checks_passed": {k: v["passed"] for k, v in checks.items()}}, indent=2))


if __name__ == "__main__":
    main()
