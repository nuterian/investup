from __future__ import annotations

import datetime as dt

import pytest

from investup import backtest


def _scored(con, rows):
    con.execute(
        "CREATE OR REPLACE TEMP TABLE scored (as_of DATE, cik BIGINT, entity_name VARCHAR, "
        "sector VARCHAR, y INT, model VARCHAR, score DOUBLE, prob DOUBLE, reason VARCHAR)"
    )
    con.executemany(
        "INSERT INTO scored VALUES (DATE '2020-01-01', ?, 'x', 's', ?, ?, ?, ?, '')", rows
    )


def test_metrics_on_a_hand_checked_example(con):
    # Scores 4 > 3 > 2 > 1 with labels 1, 0, 1, 0.
    # AUC: of the 4 positive/negative pairs, 3 are ordered correctly -> 0.75.
    # Average precision: positives at ranks 1 and 3 -> (1/1 + 2/3) / 2 = 0.8333.
    _scored(
        con,
        [
            (1, 1, "m", 0.9, 0.9),
            (2, 0, "m", 0.7, 0.7),
            (3, 1, "m", 0.4, 0.4),
            (4, 0, "m", 0.1, 0.1),
        ],
    )
    m = backtest.evaluate(con)["m"]
    assert m["n"] == 4
    assert m["base_rate"] == pytest.approx(0.5)
    assert m["auc"] == pytest.approx(0.75)
    assert m["ap"] == pytest.approx((1 + 2 / 3) / 2)
    assert m["p_at_100"] == pytest.approx(0.5)  # k larger than n -> everyone
    assert m["brier"] == pytest.approx((0.01 + 0.49 + 0.36 + 0.01) / 4)


def test_constant_scores_give_auc_one_half(con):
    _scored(con, [(i, i % 2, "flat", 0.3, 0.3) for i in range(1, 21)])
    assert backtest.evaluate(con)["flat"]["auc"] == pytest.approx(0.5)


def test_months_after_and_snapshot_dates():
    assert backtest.months_after(dt.date(2019, 1, 1), 18) == dt.date(2020, 7, 1)
    assert backtest.snapshot_dates(dt.date(2020, 1, 1), dt.date(2021, 1, 1), 6) == [
        dt.date(2020, 1, 1),
        dt.date(2020, 7, 1),
        dt.date(2021, 1, 1),
    ]
