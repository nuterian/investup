"""Gradient-boosted challenger model (LightGBM).

Optional: needs the ``model`` extra (``uv sync --extra model``). It trains on the
same point-in-time feature rows as the DuckDB models and writes its scores into
the same ``scored`` table, so the backtest compares everything like for like.

Each score comes with the features that pushed it up most, taken from
LightGBM's built-in SHAP contributions (``pred_contrib=True``).

Calibration: boosted trees trained on overlapping snapshots are over-confident
at the top, and base rates drift over time. We hold out the most recent
training snapshots, fit the model on the rest, and fit a Platt correction
(logistic on the raw score) to the held-out predictions. The final model is
trained on all training rows and its raw scores go through that correction.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import duckdb

try:  # optional dependency
    import lightgbm as lgb
    import numpy as np
except ImportError:  # pragma: no cover - exercised only without the extra
    lgb = None
    np = None

NUMERIC = (
    "months_since_last_raise",
    "months_since_first_filing",
    "age_years",
    "n_offerings",
    "n_raises_last_24m",
    "log_total_raised",
    "log_raised_last_12m",
    "log_raised_last_24m",
    "log_last_raise_amount",
    "log_largest_round",
    "last_total_investors",
    "max_investors",
    "last_offering_open",
    "has_crowdfunded",
    "has_filed_ipo_registration",
    "n_people",
    "team_prior_companies",
    "team_prior_public_companies",
    "sector_heat",
    "raised_24m_pct_in_sector",
)
CATEGORICAL = ("sector", "state", "last_revenue_range")
FEATURES = NUMERIC + CATEGORICAL

LABELS = {
    "months_since_last_raise": "months since last raise",
    "months_since_first_filing": "months since first filing",
    "age_years": "company age",
    "n_offerings": "offerings so far",
    "n_raises_last_24m": "raises in last 24m",
    "log_total_raised": "total raised",
    "log_raised_last_12m": "raised in last 12m",
    "log_raised_last_24m": "raised in last 24m",
    "log_last_raise_amount": "last raise size",
    "log_largest_round": "largest round so far",
    "last_total_investors": "investors in last raise",
    "max_investors": "most investors in a raise",
    "last_offering_open": "offering still open",
    "has_crowdfunded": "has crowdfunded",
    "has_filed_ipo_registration": "has filed an S-1/F-1",
    "n_people": "people named on filings",
    "team_prior_companies": "team's prior companies",
    "team_prior_public_companies": "team's prior IPO companies",
    "sector_heat": "sector heat",
    "raised_24m_pct_in_sector": "24m raise percentile in sector",
    "sector": "sector",
    "state": "state",
    "last_revenue_range": "revenue range",
}

PARAMS = {
    "objective": "binary",
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_data_in_leaf": 200,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "cat_smooth": 20,
    "seed": 7,
    "deterministic": True,
    "num_threads": os.cpu_count() or 4,
    "verbose": -1,
}
NUM_ROUNDS = 300
CALIBRATION_SNAPSHOTS = 2  # most recent training snapshots held out for calibration


def available() -> bool:
    return lgb is not None


def _matrix(con: duckdb.DuckDBPyConnection, table: str, categories: dict[str, list[str]]):
    cols = ", ".join(
        [f"CAST({c} AS DOUBLE) AS {c}" for c in NUMERIC]
        + [f"{c}::VARCHAR AS {c}" for c in CATEGORICAL]
    )
    data = con.execute(
        f"SELECT {cols}, y, date_diff('day', DATE '1970-01-01', as_of) AS as_of_day FROM {table}"
    ).fetchnumpy()
    columns = []
    for c in NUMERIC:
        col = data[c]
        columns.append(
            np.ma.filled(col.astype(float), np.nan)
            if np.ma.isMaskedArray(col)
            else col.astype(float)
        )
    for c in CATEGORICAL:
        index = {v: i for i, v in enumerate(categories[c])}
        values = data[c]
        values = values.filled(None) if np.ma.isMaskedArray(values) else values
        columns.append(np.array([index.get(v, -1) for v in values], dtype=float))
    y = data["y"]
    y = np.ma.filled(y, 0) if np.ma.isMaskedArray(y) else y
    return np.column_stack(columns), np.asarray(y, dtype=float), np.asarray(data["as_of_day"])


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def platt_fit(raw: np.ndarray, y: np.ndarray, iters: int = 50) -> tuple[float, float]:
    """Fit p = sigmoid(a * raw + b) by Newton's method on log loss."""
    a, b = 1.0, 0.0
    for _ in range(iters):
        p = _sigmoid(a * raw + b)
        g = p - y
        w = p * (1 - p)
        grad = np.array([np.dot(g, raw), g.sum()])
        hess = np.array(
            [[np.dot(w, raw * raw), np.dot(w, raw)], [np.dot(w, raw), w.sum()]]
        ) + 1e-6 * np.eye(2)
        step = np.linalg.solve(hess, grad)
        a, b = a - step[0], b - step[1]
        if np.abs(step).max() < 1e-8:
            break
    return float(a), float(b)


def _train(x, y, cat_idx):
    dataset = lgb.Dataset(
        x, y, feature_name=list(FEATURES), categorical_feature=cat_idx, free_raw_data=False
    )
    return lgb.train(PARAMS, dataset, num_boost_round=NUM_ROUNDS)


def _calibrator(x, y, days, cat_idx) -> tuple[float, float]:
    """Platt parameters from a time-held-out fit, or identity if there isn't enough data."""
    snapshots = np.unique(days)
    if len(snapshots) <= CALIBRATION_SNAPSHOTS:
        return 1.0, 0.0
    cutoff = snapshots[-CALIBRATION_SNAPSHOTS]
    fit, hold = days < cutoff, days >= cutoff
    if y[hold].sum() < 10 or y[fit].sum() < 10:
        return 1.0, 0.0
    booster = _train(x[fit], y[fit], cat_idx)
    return platt_fit(booster.predict(x[hold], raw_score=True), y[hold])


def _categories(con: duckdb.DuckDBPyConnection, table: str) -> dict[str, list[str]]:
    out = {}
    for c in CATEGORICAL:
        rows = con.execute(
            f"SELECT {c}::VARCHAR FROM {table} WHERE {c} IS NOT NULL "
            f"GROUP BY 1 HAVING count(*) >= 50 ORDER BY 1"
        ).fetchall()
        out[c] = [r[0] for r in rows]
    return out


def _reason(contrib_row, x_row, categories: dict[str, list[str]], top: int = 3) -> str:
    order = np.argsort(-contrib_row[:-1])  # last column is the bias term
    parts = []
    for i in order[:top]:
        if contrib_row[i] <= 0:
            break
        name = FEATURES[i]
        value = x_row[i]
        if name in CATEGORICAL:
            cats = categories[name]
            shown = cats[int(value)] if 0 <= value < len(cats) else "other"
        elif name.startswith("log_"):
            shown = f"${np.expm1(value) / 1e6:,.1f}M"
        elif np.isnan(value):
            shown = "unknown"
        elif name == "raised_24m_pct_in_sector":
            shown = f"top {max(1, round(100 * (1 - value)))}%"
        else:
            shown = f"{value:.3g}"
        parts.append(f"{LABELS[name]}: {shown}")
    return " · ".join(parts) or "no strong positive signals"


def fit_and_score(con: duckdb.DuckDBPyConnection, model: str = "gbm") -> list[tuple[str, float]]:
    """Train on temp table `train`, score temp table `test`, append to `scored`.

    Returns mean |SHAP| per feature over the test rows (global importance).
    """
    if not available():
        raise RuntimeError("LightGBM isn't installed; run `uv sync --extra model`.")
    categories = _categories(con, "train")
    x_train, y_train, days = _matrix(con, "train", categories)
    x_test, _, _ = _matrix(con, "test", categories)

    cat_idx = [FEATURES.index(c) for c in CATEGORICAL]
    a, b = _calibrator(x_train, y_train, days, cat_idx)
    booster = _train(x_train, y_train, cat_idx)
    prob = _sigmoid(a * booster.predict(x_test, raw_score=True) + b)
    contrib = booster.predict(x_test, pred_contrib=True)

    meta = con.execute("SELECT as_of, cik, entity_name, sector, y FROM test").fetchall()
    with tempfile.NamedTemporaryFile("w", suffix=".tsv", delete=False) as f:
        for (as_of, cik, name, sector, y), p, c, x in zip(meta, prob, contrib, x_test, strict=True):
            reason = _reason(c, x, categories)
            clean = (name or "").replace("\t", " ")
            f.write(
                f"{as_of}\t{cik}\t{clean}\t{sector}\t{y}\t{model}\t{float(p):.17g}\t{float(p):.17g}\t{reason}\n"
            )
        path = f.name
    try:
        con.execute(
            """
            INSERT INTO scored
            SELECT * FROM read_csv(?, delim='\t', header=false, quote='', escape='',
                columns={'as_of': 'DATE', 'cik': 'BIGINT', 'entity_name': 'VARCHAR',
                         'sector': 'VARCHAR', 'y': 'INTEGER', 'model': 'VARCHAR',
                         'score': 'DOUBLE', 'prob': 'DOUBLE', 'reason': 'VARCHAR'})
            """,
            [path],
        )
    finally:
        Path(path).unlink(missing_ok=True)

    mean_abs = np.abs(contrib[:, :-1]).mean(axis=0)
    return sorted(
        ((LABELS[f], float(v)) for f, v in zip(FEATURES, mean_abs, strict=True)),
        key=lambda t: -t[1],
    )
