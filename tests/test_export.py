from __future__ import annotations

import datetime as dt
import json

from investup import export
from investup.formd import load


def test_export_writes_site_files(con, sample_quarters, tmp_path):
    load.load_dir(con, sample_quarters)
    out = tmp_path / "site"
    sizes = export.export(
        con, out, model="cell", details_since=dt.date(2015, 1, 1), backtests=tmp_path / "none"
    )
    assert set(sizes) == {"universe.json", "lists.json", "summary.json", "search.json", "c/*.json"}

    universe = json.loads((out / "universe.json").read_text())
    rows = [dict(zip(universe["columns"], r, strict=True)) for r in universe["rows"]]
    acme = next(r for r in rows if r["cik"] == 1001)
    assert acme["name"] == "Acme Robotics, Inc."
    assert acme["total_raised"] == 8_500_000
    assert 0 <= acme["p_step"] <= 1

    summary = json.loads((out / "summary.json").read_text())
    assert summary["data_end"] == "2019-06-01"
    assert summary["quarter"]["this"]["companies"] == 1  # Acme's 2019 raise

    lists = json.loads((out / "lists.json").read_text())
    assert lists["biggest"] == [{"cik": 1001, "new_money": 5_000_000}]

    search = json.loads((out / "search.json").read_text())
    assert [r[0] for r in search["rows"]] == [1001, 3003]

    shard = json.loads((out / "c" / f"{1001 % 1024:03x}.json").read_text())
    detail = shard["1001"]
    assert [t[1] for t in detail["timeline"]] == [2_000_000, 1_500_000, 5_000_000]
    assert detail["people"][0]["name"] == "Ada Lovelace"
    # Ada is also on Beta Bio's filings, so she shows up with another company.
    assert any(o["cik"] == 3003 for o in detail["people"][0]["other"])


def test_hit_rate_lookup():
    bands = [
        {"low": 0.0, "high": 0.5, "n": 10, "observed": 0.01},
        {"low": 0.5, "high": 0.99, "n": 10, "observed": 0.05},
        {"low": 0.99, "high": 1.0, "n": 10, "observed": 0.2},
    ]
    assert export.hit_rate(bands, 0.2) == 0.01
    assert export.hit_rate(bands, 0.995) == 0.2
    assert export.hit_rate(bands, 1.0) == 0.2
    assert export.hit_rate(bands, None) is None


def test_monotone_pools_out_of_order_bands():
    bands = [
        {"low": 0.0, "high": 0.9, "n": 90, "observed": 0.05},
        {"low": 0.9, "high": 0.99, "n": 9, "observed": 0.20},
        {"low": 0.99, "high": 1.0, "n": 1, "observed": 0.10},
    ]
    out = export.monotone(bands)
    assert [(b["low"], b["high"], b["n"]) for b in out] == [(0.0, 0.9, 90), (0.9, 1.0, 10)]
    assert out[1]["observed"] == (0.2 * 9 + 0.1) / 10


def test_check_flags_stale_or_thin_exports(con, sample_quarters, tmp_path):
    load.load_dir(con, sample_quarters)
    out = tmp_path / "site"
    export.export(con, out, model="cell", details_since=dt.date(2015, 1, 1), backtests=tmp_path)
    problems = export.check(out)
    assert any("days ago" in p for p in problems)  # sample data ends in 2019
    assert any("scored companies" in p for p in problems)
    assert any("track record" in p for p in problems)
    assert export.check(tmp_path / "missing") != []
