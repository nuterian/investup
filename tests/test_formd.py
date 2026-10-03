from __future__ import annotations

import datetime as dt

import pytest

from conftest import OFFERING_COLS, filing, write_quarter_zip
from investup import ledger
from investup.formd import download, load
from investup.formd.schema import SchemaError


def build(con, src):
    load.load_dir(con, src)
    ledger.build(con)


def test_load_counts_and_excludes_funds(con, sample_quarters):
    build(con, sample_quarters)
    ciks = {r[0] for r in con.execute("SELECT DISTINCT cik FROM raise_event").fetchall()}
    assert ciks == {1001, 3003}  # fund 2002 and co-issuer 9999 excluded


def test_new_money_from_amendment_chain(con, sample_quarters):
    build(con, sample_quarters)
    rows = con.execute(
        "SELECT accession_number, is_new_offering, new_money, event_date FROM raise_event "
        "WHERE cik = 1001 ORDER BY known_at"
    ).fetchall()
    assert rows == [
        ("0001-16-000001", True, 2_000_000, dt.date(2016, 2, 15)),
        ("0001-17-000001", False, 1_500_000, dt.date(2017, 2, 20)),
        ("0001-19-000001", True, 5_000_000, dt.date(2019, 5, 20)),
    ]


def test_snapshot_does_not_see_the_future(con, sample_quarters):
    build(con, sample_quarters)
    snap = con.execute(
        "SELECT entity_name, n_offerings, total_raised, months_since_last_raise "
        "FROM company_snapshot(DATE '2016-12-31') WHERE cik = 1001"
    ).fetchone()
    assert snap == ("Acme Robotics Inc", 1, 2_000_000, 9)

    later = con.execute(
        "SELECT entity_name, n_offerings, total_raised FROM company_snapshot(DATE '2020-01-01') "
        "WHERE cik = 1001"
    ).fetchone()
    assert later == ("Acme Robotics, Inc.", 2, 8_500_000)

    # Nothing filed after the snapshot date can appear in it.
    assert (
        con.execute(
            "SELECT count(*) FROM company_snapshot(DATE '2016-03-31') WHERE cik = 3003"
        ).fetchone()[0]
        == 0
    )


def test_raised_again_label(con, sample_quarters):
    build(con, sample_quarters)
    labels = dict(
        con.execute(
            "SELECT cik, raised_again FROM raised_again_label(DATE '2016-12-31', 18)"
        ).fetchall()
    )
    assert labels == {1001: True, 3003: False}

    short = dict(
        con.execute(
            "SELECT cik, raised_again FROM raised_again_label(DATE '2016-12-31', 1)"
        ).fetchall()
    )
    assert short[1001] is False


def test_reloading_a_quarter_is_idempotent(con, sample_quarters):
    build(con, sample_quarters)
    load.load_zip(con, sample_quarters / "2016q1_d.zip")
    n = con.execute(
        "SELECT count(*) FROM stg_formd_submission WHERE source_quarter = '2016q1'"
    ).fetchone()[0]
    assert n == 1


def test_alias_column_names_are_accepted(con, tmp_path):
    cols = ["DATEOFFIRSTSALE" if c == "SALE_DATE" else c for c in OFFERING_COLS]
    f = filing(
        "0005-20-000001",
        "5005",
        "Delta AI",
        "2020-01-10",
        "750000",
        file_num="021-5",
        first_sale="2020-01-02",
    )
    path = write_quarter_zip(tmp_path, "2020q1", [f], offering_cols=cols)
    load.load_zip(con, path)
    ledger.build(con)
    assert con.execute("SELECT event_date FROM raise_event WHERE cik = 5005").fetchone()[
        0
    ] == dt.date(2020, 1, 2)


def test_missing_required_column_fails_loudly(con, tmp_path):
    cols = ["SOLD" if c == "TOTALAMOUNTSOLD" else c for c in OFFERING_COLS]
    f = filing("0006-20-000001", "6006", "Echo", "2020-01-10", "1", file_num="021-6")
    path = write_quarter_zip(tmp_path, "2020q1", [f], offering_cols=cols)
    with pytest.raises(SchemaError, match="total_amount_sold"):
        load.load_zip(con, path)
    load.ensure_staging(con)
    assert con.execute("SELECT count(*) FROM stg_formd_submission").fetchone()[0] == 0


def test_quarter_helpers():
    assert download.parse_quarter("2015Q3") == (2015, 3)
    with pytest.raises(ValueError):
        download.parse_quarter("2015-3")
    assert download.quarter_range((2015, 3), (2016, 2)) == [
        (2015, 3),
        (2015, 4),
        (2016, 1),
        (2016, 2),
    ]
    assert download.last_complete_quarter(dt.date(2026, 10, 3)) == (2026, 3)
    assert download.last_complete_quarter(dt.date(2026, 2, 1)) == (2025, 4)


def test_download_requires_contact_user_agent(monkeypatch, tmp_path):
    monkeypatch.delenv("INVESTUP_USER_AGENT", raising=False)
    with pytest.raises(RuntimeError, match="INVESTUP_USER_AGENT"):
        download.download_quarter(2020, 1, tmp_path)
