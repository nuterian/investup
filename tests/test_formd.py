from __future__ import annotations

import datetime as dt

import pytest

from conftest import OFFERING_COLS, filing, write_quarter_zip
from investup import ledger, sec
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
    assert sec.parse_quarter("2015Q3") == (2015, 3)
    with pytest.raises(ValueError):
        sec.parse_quarter("2015-3")
    assert sec.quarter_range((2015, 3), (2016, 2)) == [
        (2015, 3),
        (2015, 4),
        (2016, 1),
        (2016, 2),
    ]
    assert sec.last_complete_quarter(dt.date(2026, 10, 3)) == (2026, 3)
    assert sec.last_complete_quarter(dt.date(2026, 2, 1)) == (2025, 4)


def test_download_requires_contact_user_agent(monkeypatch):
    monkeypatch.delenv("INVESTUP_USER_AGENT", raising=False)
    with pytest.raises(RuntimeError, match="INVESTUP_USER_AGENT"):
        sec.user_agent()


def test_parse_index_handles_mixed_paths_and_suffixes():
    html = """
    <a href="/files/datastandardsinnovation/data/form-d-data-sets/2026q2_d.zip">2026 Q2</a>
    <a href="/files/structureddata/data/form-d-data-sets/2008q2_d_0.zip">2008 Q2</a>
    <a href="https://www.sec.gov/files/structureddata/data/form-d-data-sets/2015q1_d.zip">x</a>
    <a href="/files/Form_D.pdf">Form D</a>
    """
    assert download.parse_index(html) == {
        (
            2026,
            2,
        ): "https://www.sec.gov/files/datastandardsinnovation/data/form-d-data-sets/2026q2_d.zip",
        (2008, 2): "https://www.sec.gov/files/structureddata/data/form-d-data-sets/2008q2_d_0.zip",
        (2015, 1): "https://www.sec.gov/files/structureddata/data/form-d-data-sets/2015q1_d.zip",
    }


def test_test_filings_are_excluded(con, tmp_path):
    live = filing("0007-20-000001", "7007", "Live Co", "2020-01-10", "100", file_num="021-7")
    test = filing(
        "0008-20-000001", "8008", "Test Co", "2020-01-10", "100", file_num="021-8", test=True
    )
    load.load_zip(con, write_quarter_zip(tmp_path, "2020q1", [live, test]))
    ledger.build(con)
    assert con.execute("SELECT list(cik) FROM formd_filing").fetchone()[0] == [7007]


def test_same_day_correction_replaces_typo(con, tmp_path):
    typo = filing(
        "0009-18-000001",
        "9009",
        "Livo Health",
        "2018-04-23",
        "104999999994",
        file_num="021-9",
        investors="15",
    )
    fixed = filing(
        "0009-18-000002",
        "9009",
        "Livo Health",
        "2018-04-23",
        "104999994",
        file_num="021-9",
        sub_type="D/A",
        investors="15",
    )
    load.load_zip(con, write_quarter_zip(tmp_path, "2018q2", [typo, fixed]))
    ledger.build(con)
    assert con.execute(
        "SELECT list(accession_number), sum(new_money) FROM raise_event WHERE cik = 9009"
    ).fetchone() == (["0009-18-000002"], 104_999_994)


def test_implausible_amounts_are_flagged_and_excluded(con, tmp_path):
    shell = filing(
        "0010-24-000001",
        "1010",
        "Shell Holding Co",
        "2024-07-09",
        "48000000000",
        file_num="021-10",
        investors="1",
    )
    load.load_zip(con, write_quarter_zip(tmp_path, "2024q3", [shell]))
    ledger.build(con)
    assert (
        con.execute("SELECT is_suspect_amount FROM raise_event WHERE cik = 1010").fetchone()[0]
        is True
    )
    assert con.execute(
        "SELECT total_raised, last_raise_at FROM company_snapshot(DATE '2025-01-01') "
        "WHERE cik = 1010"
    ).fetchone() == (0, None)


def test_sectors(con, sample_quarters):
    build(con, sample_quarters)
    rows = dict(
        con.execute(
            "SELECT cik, (sector, is_venture_sector) FROM company_snapshot(DATE '2020-01-01')"
        ).fetchall()
    )
    assert rows[1001] == ("Technology", True)
    assert rows[3003] == ("Health Care", True)
