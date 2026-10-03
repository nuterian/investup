from __future__ import annotations

import pytest

from investup import backtest, gbm

pytest.importorskip("lightgbm")


def _table(con, name: str, n: int, offset: int) -> None:
    """Rows where more recent raises -> label 1, so a model must find the signal."""
    numeric = ", ".join(
        f"0.0 AS {c}"
        for c in gbm.NUMERIC
        if c not in ("months_since_last_raise", "n_raises_last_24m")
    )
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE {name} AS
        SELECT
            DATE '2020-01-01' AS as_of,
            {offset} + i AS cik,
            'Co ' || i AS entity_name,
            CASE WHEN i % 2 = 0 THEN 'Technology' ELSE 'Health Care' END AS sector,
            'CA' AS state,
            'Decline to Disclose' AS last_revenue_range,
            (i % 36)::DOUBLE AS months_since_last_raise,
            (i % 4)::DOUBLE AS n_raises_last_24m,
            {numeric},
            CASE WHEN i % 36 < 9 THEN 1 ELSE 0 END AS y
        FROM range({n}) t(i)
        """
    )


def test_gbm_learns_signal_and_explains_scores(con):
    _table(con, "train", 4000, 0)
    _table(con, "test", 720, 100_000)
    con.execute(
        "CREATE OR REPLACE TEMP TABLE scored (as_of DATE, cik BIGINT, entity_name VARCHAR, "
        "sector VARCHAR, y INT, model VARCHAR, score DOUBLE, prob DOUBLE, reason VARCHAR)"
    )
    importance = gbm.fit_and_score(con)

    metrics = backtest.evaluate(con)["gbm"]
    assert metrics["n"] == 720
    assert metrics["auc"] > 0.95
    assert importance[0][0] == "months since last raise"

    reason = con.execute("SELECT reason FROM scored ORDER BY prob DESC LIMIT 1").fetchone()[0]
    assert "months since last raise" in reason
