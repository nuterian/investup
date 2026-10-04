"""Export the data the static site reads (see docs/FRONTEND_PLAN.md).

Writes into ``out``:

* ``summary.json``: data date, quarter KPIs, funding pulse, sector and state
  momentum, model track record.
* ``universe.json``: every scored company (columnar) with both probabilities,
  percentiles, reasons and the previous quarter's bigger-round odds.
* ``lists.json``: the curated home-page lists.
* ``search.json``: name index of every operating company that raised since
  ``details_since``.
* ``c/<xxx>.json``: company detail (funding timeline, facts, people and their
  other companies), split into ``shards`` files by ``cik % shards`` (default
  1,024, about 13 KB gzipped each). The count is written to ``summary.json``.
"""

from __future__ import annotations

import datetime as dt
import json
from collections import defaultdict
from pathlib import Path

import duckdb

from investup import backtest, features

SHARDS = 1024

VENTURE_EVENT = """
    is_venture_sector(sector)
    AND is_us_state(state)
    AND NOT issuer_was_public
    AND NOT issuer_was_investment_company
    AND NOT looks_like_partnership_firm(entity_name)
    AND NOT is_suspect_amount
"""


def _name(s: str | None) -> str:
    if not s:
        return ""
    return s.title() if s.isupper() else s


def _r(x: float | None, digits: int = 4) -> float | None:
    return None if x is None else round(float(x), digits)


def _money(x: float | None) -> int | None:
    return None if x is None else int(round(float(x)))


def _date(d: dt.date | None) -> str | None:
    return None if d is None else d.isoformat()


def _write(path: Path, obj) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    path.write_text(text)
    return len(text)


def _columnar(columns: list[str], rows: list[tuple]) -> dict:
    return {"columns": columns, "rows": [list(r) for r in rows]}


def monotone(bands: list[dict]) -> list[dict]:
    """Pool adjacent bands (weighted by size) until hit rates never fall as rank
    rises, so a higher-ranked company never shows lower odds. Small top bands
    are otherwise noisy."""
    blocks = [dict(b) for b in bands]
    i = 0
    while i < len(blocks) - 1:
        a, b = blocks[i], blocks[i + 1]
        if b["observed"] < a["observed"]:
            n = a["n"] + b["n"]
            merged = {
                "low": a["low"],
                "high": b["high"],
                "n": n,
                "observed": (a["observed"] * a["n"] + b["observed"] * b["n"]) / n,
            }
            blocks[i : i + 2] = [merged]
            i = max(i - 1, 0)
        else:
            i += 1
    return blocks


def _bands(backtests: Path, label: str) -> list[dict]:
    path = backtests / f"{label}.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    bands = data.get("hit_rate_by_rank", {})
    return monotone(bands.get("gbm") or bands.get("cell") or [])


def hit_rate(bands: list[dict], pct: float | None) -> float | None:
    """Historical hit rate for the rank band a percentile falls in."""
    if pct is None:
        return None
    for b in bands:
        if b["low"] <= pct < b["high"] or (pct >= 1.0 and b["high"] >= 1.0):
            return _r(b["observed"])
    return None


def _track_record(backtests: Path) -> dict:
    out = {}
    for label in ("step_up", "went_public", "next_round"):
        path = backtests / f"{label}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        best = "gbm" if "gbm" in data["models"] else "cell"
        m = data["models"][best]
        out[label] = {
            "model": best,
            "horizon_months": data["horizon_months"],
            "test_years": f"{data['test_dates'][0][:4]}–{data['test_dates'][-1][:4]}",
            "auc": _r(m["auc"], 3),
            "base_rate": _r(m["base_rate"]),
            "p_at_100": _r(m["p_at_100"]),
            "lift_at_100": _r(m["p_at_100"] / m["base_rate"], 2) if m["base_rate"] else None,
            "hit_rate_by_rank": _bands(backtests, label),
        }
    return out


def score(con: duckdb.DuckDBPyConnection, model: str | None = None) -> dict:
    """Score the universe now and one quarter earlier. Returns metadata."""
    features.build(con)
    end = backtest.data_end(con)
    prev = backtest.months_after(end, -3)
    model, _ = backtest.score_current(con, label="step_up", horizon=18, model=model, table="x_step")
    backtest.score_current(con, label="went_public", horizon=36, model=model, table="x_ipo")
    backtest.score_current(
        con, label="step_up", horizon=18, model=model, table="x_prev_step", as_of=prev
    )
    con.execute(
        f"CREATE OR REPLACE TEMP TABLE x_features AS SELECT * FROM features(DATE '{end}', 36)"
    )
    return {"end": end, "prev": prev, "model": model}


def universe_rows(
    con: duckdb.DuckDBPyConnection, end: dt.date, backtests: Path
) -> tuple[list[str], list[tuple]]:
    """One row per scored company. `hit_step` / `hit_ipo` are the historical hit
    rates (from the backtest) of the rank band each company falls in. These are
    the numbers to show; the raw probabilities are over-confident at the top."""
    columns = [
        "cik", "name", "state", "sector", "first_filing", "last_raise", "total_raised",
        "largest_round", "rounds", "p_step", "p_ipo", "pct_step", "pct_ipo", "hit_step",
        "hit_ipo", "repeat_founder", "prev_p_step", "step_reason", "ipo_reason",
    ]  # fmt: skip
    step_bands, ipo_bands = _bands(backtests, "step_up"), _bands(backtests, "went_public")
    rows = con.execute(
        f"""
        SELECT
            f.cik,
            f.entity_name,
            f.state,
            f.sector,
            cs.first_filing_at,
            cs.last_raise_at,
            cs.total_raised,
            exp(f.log_largest_round) - 1,
            cs.n_offerings,
            s.prob,
            i.prob,
            percent_rank() OVER (ORDER BY s.prob),
            percent_rank() OVER (ORDER BY i.prob),
            f.team_prior_public_companies > 0,
            p.prob,
            s.reason,
            i.reason
        FROM x_features AS f
        JOIN x_step AS s USING (cik)
        JOIN x_ipo AS i USING (cik)
        JOIN company_snapshot(DATE '{end}') AS cs USING (cik)
        LEFT JOIN x_prev_step AS p USING (cik)
        ORDER BY s.prob DESC, hash(f.cik)
        """
    ).fetchall()
    out = []
    for r in rows:
        (cik, name, state, sector, first, last, total, largest, rounds, p_s, p_i, pct_s,
         pct_i, repeat, prev, why_s, why_i) = r  # fmt: skip
        out.append(
            (
                cik, _name(name), state, sector, _date(first), _date(last), _money(total),
                _money(largest), rounds, _r(p_s), _r(p_i), _r(pct_s, 4), _r(pct_i, 4),
                hit_rate(step_bands, pct_s), hit_rate(ipo_bands, pct_i), bool(repeat), _r(prev),
                why_s, why_i,
            )
        )  # fmt: skip
    return columns, out


def build_lists(
    con: duckdb.DuckDBPyConnection,
    universe: list[dict],
    end: dt.date,
    prev: dt.date,
    top: int,
) -> dict:
    year_ago = backtest.months_after(end, -12).isoformat()

    def pick(rows, key, n=top):
        return [r["cik"] for r in sorted(rows, key=key)[:n]]

    active = [u for u in universe if (u["last_raise"] or "") >= year_ago]
    lists = {
        "step_up": pick(active, lambda u: -(u["p_step"] or 0)),
        "ipo_watch": pick(
            [u for u in universe if (u["total_raised"] or 0) >= 5_000_000],
            lambda u: -(u["p_ipo"] or 0),
        ),
        "movers": pick(
            [u for u in active if u["prev_p_step"] is not None],
            lambda u: -((u["p_step"] or 0) - u["prev_p_step"]),
        ),
        "repeat_founders": pick(
            [u for u in universe if u["repeat_founder"] and (u["first_filing"] or "") >= year_ago],
            lambda u: -(u["p_step"] or 0),
        ),
    }
    lists["biggest"] = [
        {"cik": cik, "new_money": _money(m)}
        for cik, m in con.execute(
            f"""
            SELECT r.cik, sum(r.new_money) AS m
            FROM raise_event AS r
            JOIN x_features USING (cik)
            WHERE r.known_at > ? AND r.known_at <= ? AND NOT r.is_suspect_amount
            GROUP BY r.cik ORDER BY m DESC, hash(r.cik) LIMIT {max(top, 300)}
            """,
            [prev, end],
        ).fetchall()
    ]
    lists["ipo_pipeline"] = [
        {"cik": cik, "name": _name(name), "filed": _date(filed)}
        for cik, name, filed in con.execute(
            f"""
            SELECT m.cik, cs.entity_name, m.first_ipo_registration_at
            FROM edgar_milestone AS m
            JOIN company_snapshot(DATE '{end}') AS cs USING (cik)
            WHERE m.first_ipo_registration_at > ? AND m.first_ipo_registration_at <= ?
              AND cs.is_venture_sector AND is_us_state(cs.state)
              AND NOT cs.is_investment_company
            ORDER BY cs.total_raised DESC NULLS LAST, hash(m.cik) LIMIT {max(top, 200)}
            """,
            [prev, end],
        ).fetchall()
    ]
    return lists


def build_summary(
    con: duckdb.DuckDBPyConnection, end: dt.date, prev: dt.date, model: str, backtests: Path
) -> dict:
    def window(lo: dt.date, hi: dt.date) -> dict:
        companies, money = con.execute(
            f"""
            SELECT count(DISTINCT cik), sum(new_money) FROM raise_event
            WHERE known_at > ? AND known_at <= ? AND new_money > 0 AND {VENTURE_EVENT}
            """,
            [lo, hi],
        ).fetchone()
        return {"companies": companies, "money": _money(money)}

    year_ago_end = backtest.months_after(end, -12)
    year_ago_prev = backtest.months_after(prev, -12)
    new_companies = con.execute(
        f"""
        SELECT count(*) FROM (
            SELECT cik, min(known_at) AS first FROM raise_event WHERE {VENTURE_EVENT} GROUP BY cik
        ) WHERE first > ? AND first <= ?
        """,
        [prev, end],
    ).fetchone()[0]
    pulse = con.execute(
        f"""
        SELECT strftime(date_trunc('quarter', known_at), '%Y-%m-%d'),
               count(DISTINCT cik), sum(new_money)
        FROM raise_event
        WHERE new_money > 0 AND known_at >= DATE '2009-07-01' AND known_at <= ?
          AND {VENTURE_EVENT}
        GROUP BY 1 ORDER BY 1
        """,
        [end],
    ).fetchall()
    sectors = con.execute(
        f"""
        SELECT sector,
               count(DISTINCT cik) FILTER (WHERE known_at > ?)                   AS last_12m,
               count(DISTINCT cik) FILTER (WHERE known_at <= ?)                  AS prior_12m,
               sum(new_money) FILTER (WHERE known_at > ?)                        AS money_12m
        FROM raise_event
        WHERE new_money > 0 AND known_at > ? AND known_at <= ? AND {VENTURE_EVENT}
        GROUP BY sector ORDER BY last_12m DESC
        """,
        [year_ago_end, year_ago_end, year_ago_end, backtest.months_after(end, -24), end],
    ).fetchall()
    states = con.execute(
        f"""
        SELECT state, count(DISTINCT cik) AS n, sum(new_money) AS money
        FROM raise_event
        WHERE new_money > 0 AND known_at > ? AND known_at <= ? AND {VENTURE_EVENT}
        GROUP BY state ORDER BY n DESC LIMIT 10
        """,
        [year_ago_end, end],
    ).fetchall()
    base = con.execute("SELECT avg(prob) FROM x_step").fetchone()[0]
    base_ipo = con.execute("SELECT avg(prob) FROM x_ipo").fetchone()[0]
    return {
        "data_end": end.isoformat(),
        "prev_date": prev.isoformat(),
        "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "model": model,
        "quarter": {
            "this": window(prev, end),
            "year_ago": window(year_ago_prev, year_ago_end),
            "new_companies": new_companies,
        },
        "typical": {"p_step": _r(base), "p_ipo": _r(base_ipo)},
        "pulse": [{"q": q, "companies": n, "money": _money(m)} for q, n, m in pulse],
        "sectors": [
            {"sector": s, "last_12m": a, "prior_12m": b, "money_12m": _money(m)}
            for s, a, b, m in sectors
        ],
        "states": [{"state": s, "companies": n, "money": _money(m)} for s, n, m in states],
        "track_record": _track_record(backtests),
    }


def search_rows(con: duckdb.DuckDBPyConnection, since: dt.date) -> list[tuple]:
    rows = con.execute(
        """
        SELECT cik, arg_max(entity_name, known_at), arg_max(state, known_at), year(max(known_at))
        FROM raise_event
        WHERE known_at >= ?
        GROUP BY cik
        ORDER BY cik
        """,
        [since],
    ).fetchall()
    return [(cik, _name(n), s, y) for cik, n, s, y in rows]


def detail_shards(
    con: duckdb.DuckDBPyConnection, since: dt.date, end: dt.date, shards: int = SHARDS
) -> dict:
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE x_ciks AS
        SELECT DISTINCT cik FROM raise_event WHERE known_at >= ?
        """,
        [since],
    )
    details: dict[int, dict] = {}
    facts = con.execute(
        f"""
        SELECT cs.cik, cs.entity_name, cs.state, cs.sector, cs.industry_group, cs.year_of_inc,
               cs.first_filing_at, cs.last_raise_at, cs.total_raised, cs.n_offerings,
               cs.last_total_investors, cs.max_investors, cs.last_revenue_range,
               m.went_public_at, m.first_ipo_registration_at, cs.is_investment_company
        FROM company_snapshot(DATE '{end}') AS cs
        JOIN x_ciks USING (cik)
        LEFT JOIN edgar_milestone AS m USING (cik)
        """
    ).fetchall()
    for (cik, name, state, sector, industry, inc, first, last, total, n_off, inv_last, inv_max,
         revenue, public, s1, vehicle) in facts:  # fmt: skip
        details[cik] = {
            "name": _name(name),
            "state": state,
            "sector": sector,
            "industry": industry,
            "year_of_inc": inc,
            "first_filing": _date(first),
            "last_raise": _date(last),
            "total_raised": _money(total),
            "rounds": n_off,
            "investors_last": inv_last,
            "investors_max": inv_max,
            "revenue_range": revenue,
            "went_public": _date(public),
            "s1_filed": _date(s1),
            "vehicle": bool(vehicle),
            "timeline": [],
            "people": [],
        }

    for cik, known, money, new_round, acc in con.execute(
        """
        SELECT r.cik, r.known_at, r.new_money, r.is_new_offering, r.accession_number
        FROM raise_event AS r JOIN x_ciks USING (cik)
        WHERE NOT r.is_suspect_amount
        ORDER BY r.cik, r.known_at, r.accession_number
        """
    ).fetchall():
        if cik in details:
            details[cik]["timeline"].append([_date(known), _money(money), bool(new_round), acc])

    # People are matched across companies by full name only. The filing's state
    # field often follows the company's address, so name + state misses moves.
    # Names linked to more than 20 companies (common names, placement agents)
    # are left unlinked.
    people = con.execute(
        f"""
        WITH person_name AS (
            SELECT DISTINCT
                upper(trim(p.first_name)) || ' ' || upper(trim(p.last_name)) AS name_key,
                r.cik
            FROM stg_formd_related_person AS p
            JOIN raise_event AS r USING (accession_number)
            WHERE length(trim(coalesce(p.first_name, ''))) > 1
              AND length(trim(coalesce(p.last_name, ''))) > 1
        ), degree AS (
            SELECT name_key, count(*) AS n FROM person_name GROUP BY name_key
        ), latest AS (
            SELECT r.cik, arg_max(r.accession_number, r.known_at) AS accession_number
            FROM raise_event AS r JOIN x_ciks USING (cik)
            GROUP BY r.cik
        ), named AS (
            SELECT
                l.cik,
                trim(p.first_name) AS first,
                trim(p.last_name) AS last,
                upper(trim(p.first_name)) || ' ' || upper(trim(p.last_name)) AS name_key,
                string_agg(DISTINCT concat_ws(', ', p.relationship_1, p.relationship_2,
                                              p.relationship_3), '; ') AS roles
            FROM latest AS l
            JOIN stg_formd_related_person AS p USING (accession_number)
            WHERE length(trim(coalesce(p.last_name, ''))) > 1
            GROUP BY ALL
        ), other AS (
            SELECT
                n.cik, n.name_key,
                list(struct_pack(cik := pn.cik, name := cs.entity_name,
                                 public := year(m.went_public_at))
                     ORDER BY m.went_public_at NULLS LAST, cs.last_raise_at DESC)[:5]
                                                                   AS companies
            FROM named AS n
            JOIN degree AS d USING (name_key)
            JOIN person_name AS pn ON pn.name_key = n.name_key AND pn.cik <> n.cik
            JOIN company_snapshot(DATE '{end}') AS cs ON cs.cik = pn.cik
            LEFT JOIN edgar_milestone AS m ON m.cik = pn.cik
            WHERE d.n <= 20
            GROUP BY n.cik, n.name_key
        )
        SELECT n.cik, n.first, n.last, n.roles, o.companies
        FROM named AS n
        LEFT JOIN other AS o USING (cik, name_key)
        ORDER BY n.cik, (o.companies IS NULL), n.last, n.first
        """
    ).fetchall()
    for cik, first, last, roles, companies in people:
        if cik not in details:
            continue
        details[cik]["people"].append(
            {
                "name": _name(f"{first or ''} {last}".strip()),
                "roles": roles,
                "other": [
                    {"cik": c["cik"], "name": _name(c["name"]), "public": c["public"]}
                    for c in (companies or [])
                ],
            }
        )

    out: dict[str, dict] = defaultdict(dict)
    for cik, d in details.items():
        out[f"{cik % shards:03x}"][str(cik)] = d
    return out


def export(
    con: duckdb.DuckDBPyConnection,
    out: Path,
    *,
    model: str | None = None,
    top: int = 25,
    details_since: dt.date = dt.date(2019, 1, 1),
    backtests: Path = Path("docs/backtests"),
    shards: int = SHARDS,
) -> dict[str, int]:
    """Write all site data files. Returns bytes written per file group."""
    meta = score(con, model=model)
    end, prev = meta["end"], meta["prev"]
    sizes: dict[str, int] = {}

    columns, rows = universe_rows(con, end, backtests)
    sizes["universe.json"] = _write(out / "universe.json", _columnar(columns, rows))
    universe = [dict(zip(columns, r, strict=True)) for r in rows]

    lists = build_lists(con, universe, end, prev, top)
    sizes["lists.json"] = _write(out / "lists.json", lists)

    summary = build_summary(con, end, prev, meta["model"], backtests)
    summary["shards"] = shards
    sizes["summary.json"] = _write(out / "summary.json", summary)

    search = search_rows(con, details_since)
    sizes["search.json"] = _write(
        out / "search.json", _columnar(["cik", "name", "state", "last_year"], search)
    )

    detail = detail_shards(con, details_since, end, shards)
    sizes["c/*.json"] = sum(_write(out / "c" / f"{k}.json", v) for k, v in detail.items())
    return sizes


def check(out: Path, *, max_age_days: int = 10, min_companies: int = 10_000) -> list[str]:
    """Problems that should stop a deploy (empty list = OK)."""
    problems = []
    try:
        summary = json.loads((out / "summary.json").read_text())
        universe = json.loads((out / "universe.json").read_text())
    except (OSError, ValueError) as e:
        return [f"Can't read exported files: {e}"]
    age = (dt.date.today() - dt.date.fromisoformat(summary["data_end"])).days
    if age > max_age_days:
        problems.append(
            f"Newest filing is from {summary['data_end']} ({age} days ago); the live Form D "
            "ingest may have stopped working."
        )
    if len(universe["rows"]) < min_companies:
        problems.append(
            f"Only {len(universe['rows']):,} scored companies (expected {min_companies:,}+)."
        )
    if not summary["quarter"]["this"]["companies"]:
        problems.append("No raises in the latest quarter window.")
    if not summary.get("track_record"):
        problems.append("No backtest track record (docs/backtests/*.json missing?).")
    shards = summary.get("shards", SHARDS)
    found = len(list((out / "c").glob("*.json")))
    if found < shards * 0.9:
        problems.append(f"Only {found} of {shards} company detail files were written.")
    return problems
