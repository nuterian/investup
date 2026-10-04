from __future__ import annotations

import gzip
from pathlib import Path

from conftest import filing, write_quarter_zip
from investup import edgar, ledger
from investup.formd import load

HEADER = """Description:           Master Index of EDGAR Dissemination Feed
Last Data Received:    June 30, 2019
Comments:              webmaster@sec.gov
Anonymous FTP:         ftp://ftp.sec.gov/edgar/
Cloud HTTP:            https://www.sec.gov/Archives/




CIK|Company Name|Form Type|Date Filed|Filename
--------------------------------------------------------------------------------
"""


def write_master(dest: Path, quarter: str, rows: list[tuple[str, str, str, str]]) -> Path:
    path = dest / f"{quarter}_master.gz"
    body = "".join(
        f"{cik}|{name}|{form}|{date}|edgar/data/{cik}/x.txt\n" for cik, name, form, date in rows
    )
    with gzip.open(path, "wt", encoding="latin-1") as f:
        f.write(HEADER + body)
    return path


def test_classify():
    assert edgar.classify("10-K") == "periodic"
    assert edgar.classify("10-Q/A") == "periodic"
    assert edgar.classify("S-1/A") == "ipo_registration"
    assert edgar.classify("424B4") == "ipo_prospectus"
    assert edgar.classify("N-4") == "investment_company"
    assert edgar.classify("NPORT-P") == "investment_company"
    assert edgar.classify("C-AR") == "crowdfunding"
    assert edgar.classify("8-K") is None
    assert edgar.classify("D") is None


def test_parse_master_skips_header_and_irrelevant_forms(tmp_path):
    path = write_master(
        tmp_path,
        "2019q2",
        [("1001", "Acme", "424B4", "2019-05-10"), ("1001", "Acme", "8-K", "2019-05-11")],
    )
    with gzip.open(path, "rt", encoding="latin-1") as f:
        rows = edgar.parse_master(f)
    assert rows == [("1001", "424B4", "ipo_prospectus", "2019-05-10", "edgar/data/1001/x.txt")]


def _scenario(con, tmp_path):
    """Acme raises in 2016-17 and again in 2019, then IPOs in 2020.
    Bigco is already public when it files Form D. Beta never raises again."""
    f = [
        filing("a1", "1001", "Acme", "2016-03-01", "2000000", file_num="o1"),
        filing("a2", "1001", "Acme", "2017-02-20", "3500000", file_num="o1", sub_type="D/A"),
        filing("a3", "1001", "Acme", "2019-06-01", "5000000", file_num="o2"),
        filing("b1", "3003", "Beta", "2016-05-10", "500000", file_num="o3"),
        filing("v1", "4004", "Bigco", "2016-06-01", "9000000", file_num="o4"),
    ]
    load.load_zip(con, write_quarter_zip(tmp_path, "2019q2", f))
    edgar.load_file(
        con,
        write_master(
            tmp_path,
            "2020q3",
            [
                ("4004", "Bigco", "10-K", "2009-03-01"),
                ("1001", "Acme", "S-1", "2020-08-01"),
                ("1001", "Acme", "424B4", "2020-09-15"),
                ("1001", "Acme", "10-Q", "2020-11-10"),
            ],
        ),
    )
    ledger.build(con)


def test_public_status_is_point_in_time(con, tmp_path):
    _scenario(con, tmp_path)
    before = dict(
        con.execute("SELECT cik, is_public FROM company_snapshot(DATE '2020-01-01')").fetchall()
    )
    after = dict(
        con.execute("SELECT cik, is_public FROM company_snapshot(DATE '2021-01-01')").fetchall()
    )
    assert before == {1001: False, 3003: False, 4004: True}
    assert after[1001] is True


def test_venture_universe_excludes_public_and_stale(con, tmp_path):
    _scenario(con, tmp_path)
    ciks = [
        r[0]
        for r in con.execute(
            "SELECT cik FROM venture_universe(DATE '2017-06-01', 36) ORDER BY cik"
        ).fetchall()
    ]
    assert ciks == [1001, 3003]  # Bigco is public
    ciks = [
        r[0]
        for r in con.execute("SELECT cik FROM venture_universe(DATE '2017-06-01', 12)").fetchall()
    ]
    assert ciks == [1001]  # Beta last raised 13 months earlier


def test_next_round_ignores_more_closings_of_the_open_round(con, tmp_path):
    _scenario(con, tmp_path)
    # On 2016-06-30 Acme's round o1 is open; the 2017 amendment adds money to it,
    # which counts for raised_again but is not a new round.
    raised = dict(
        con.execute(
            "SELECT cik, raised_again FROM raised_again_label(DATE '2016-06-30', 12)"
        ).fetchall()
    )
    nxt = dict(
        con.execute(
            "SELECT cik, next_round FROM next_round_label(DATE '2016-06-30', 12)"
        ).fetchall()
    )
    assert raised[1001] is True
    assert nxt[1001] is False
    nxt_long = dict(
        con.execute(
            "SELECT cik, next_round FROM next_round_label(DATE '2016-06-30', 36)"
        ).fetchall()
    )
    assert nxt_long[1001] is True


def test_went_public_label(con, tmp_path):
    _scenario(con, tmp_path)
    labels = dict(
        con.execute(
            "SELECT cik, went_public FROM went_public_label(DATE '2019-12-31', 12)"
        ).fetchall()
    )
    assert labels == {1001: True, 3003: False, 4004: False}
    assert (
        con.execute("SELECT went_public_at FROM edgar_milestone WHERE cik = 1001")
        .fetchone()[0]
        .isoformat()
        == "2020-09-15"
    )


def test_reloading_edgar_quarter_is_idempotent(con, tmp_path):
    path = write_master(tmp_path, "2019q2", [("1001", "Acme", "10-K", "2019-05-10")])
    edgar.load_file(con, path)
    edgar.load_file(con, path)
    assert con.execute("SELECT count(*) FROM stg_edgar_index").fetchone()[0] == 1
