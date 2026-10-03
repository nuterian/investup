"""Walk-forward backtest and scoring.

For each test date T we train only on snapshots whose label window closed by T
(``as_of + horizon <= T``), then score every company in the venture universe
on T and compare with what happened over the next ``horizon`` months.

Models (all fitted in DuckDB, no ML dependencies):

* ``base_rate``: everyone gets the training base rate. The floor.
* ``recency``: a hand-written rule. More raises in the last 24 months and a
  more recent last raise rank higher.
* ``cell``: historical outcome rate for companies that looked the same
  (raise count x recency x team track record x sector), smoothed toward the
  parent cell without sector. Calibrated, and the cell itself is the
  explanation.
* ``gbm``: LightGBM on all features (see investup.gbm). Only runs when the
  ``model`` extra is installed.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

from investup import features, gbm

LABELS = ("next_round", "raised_again", "went_public")
ACTIVE_MONTHS = 36
SMOOTHING = 30.0
SQL_MODELS = ("base_rate", "recency", "cell")


def models() -> tuple[str, ...]:
    return (*SQL_MODELS, "gbm") if gbm.available() else SQL_MODELS


TOP_K = (100, 500, 1000)

CELL_SQL = """
CASE
    WHEN n_raises_last_24m >= 3 THEN '3+ raises/24m'
    WHEN n_raises_last_24m = 2 THEN '2 raises/24m'
    WHEN n_raises_last_24m = 1 THEN '1 raise/24m'
    ELSE '0 raises/24m'
END
|| ' · ' ||
CASE
    WHEN months_since_last_raise < 6 THEN 'last raise <6mo ago'
    WHEN months_since_last_raise < 12 THEN 'last raise 6-11mo ago'
    WHEN months_since_last_raise < 24 THEN 'last raise 12-23mo ago'
    ELSE 'last raise 24+mo ago'
END
|| ' · ' ||
CASE
    WHEN team_prior_public_companies > 0 THEN 'team has a prior IPO company'
    WHEN team_prior_companies > 0 THEN 'team has prior companies'
    ELSE 'first-time team'
END
"""


def months_after(d: dt.date, months: int) -> dt.date:
    y, m = divmod(d.month - 1 + months, 12)
    return dt.date(d.year + y, m + 1, d.day)


def data_end(con: duckdb.DuckDBPyConnection) -> dt.date:
    return con.execute("SELECT max(known_at) FROM raise_event").fetchone()[0]


def snapshot_dates(start: dt.date, end: dt.date, step_months: int = 6) -> list[dt.date]:
    out, d = [], start
    while d <= end:
        out.append(d)
        d = months_after(d, step_months)
    return out


def build_rows(
    con: duckdb.DuckDBPyConnection, dates: list[dt.date], horizon: int, table: str = "bt_rows"
) -> None:
    """Materialize labeled features for every snapshot date into `table`."""
    con.execute(f"DROP TABLE IF EXISTS {table}")
    for i, d in enumerate(dates):
        sql = f"SELECT * FROM labeled_features(DATE '{d}', {ACTIVE_MONTHS}, {horizon})"
        if i == 0:
            con.execute(f"CREATE TABLE {table} AS {sql}")
        else:
            con.execute(f"INSERT INTO {table} {sql}")
    con.execute(f"ALTER TABLE {table} ADD COLUMN cell VARCHAR")
    con.execute(f"UPDATE {table} SET cell = {CELL_SQL}")


def fit_and_score(
    con: duckdb.DuckDBPyConnection, rows: str, label: str, train_where: str, test_where: str
) -> None:
    """Fit the models on `train_where` rows and write scores for `test_where` rows
    into the temp table `scored` (cik, label, model, score, prob, reason)."""
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE train AS
        SELECT *, {label}::INT AS y FROM {rows} WHERE {train_where};
        CREATE OR REPLACE TEMP TABLE test AS
        SELECT *, {label}::INT AS y FROM {rows} WHERE {test_where};

        CREATE OR REPLACE TEMP TABLE cell_rates AS
        WITH g AS (SELECT avg(y) AS p FROM train),
        parent AS (
            SELECT cell, (sum(y) + {SMOOTHING} * any_value(g.p)) / (count(*) + {SMOOTHING}) AS p
            FROM train, g GROUP BY cell
        ),
        child AS (
            SELECT cell, sector, sum(y) AS pos, count(*) AS n FROM train GROUP BY cell, sector
        )
        SELECT child.cell, child.sector, child.n,
               (child.pos + {SMOOTHING} * parent.p) / (child.n + {SMOOTHING}) AS p
        FROM child JOIN parent USING (cell);

        CREATE OR REPLACE TEMP TABLE scored AS
        WITH g AS (SELECT avg(y) AS p FROM train),
        parent AS (
            SELECT cell, (sum(y) + {SMOOTHING} * any_value(g.p)) / (count(*) + {SMOOTHING}) AS p
            FROM train, g GROUP BY cell
        )
        SELECT t.as_of, t.cik, t.entity_name, t.sector, t.y, 'base_rate' AS model,
               g.p AS score, g.p AS prob, 'training base rate' AS reason
        FROM test t, g
        UNION ALL
        SELECT t.as_of, t.cik, t.entity_name, t.sector, t.y, 'recency',
               100.0 * least(t.n_raises_last_24m, 5) - t.months_since_last_raise,
               NULL, 'rule: raise count, then recency'
        FROM test t
        UNION ALL
        SELECT t.as_of, t.cik, t.entity_name, t.sector, t.y, 'cell',
               -- Rank by cell probability; break ties inside a cell with the rule.
               coalesce(c.p, parent.p, g.p)
                   + 1e-7 * (100.0 * least(t.n_raises_last_24m, 5) - t.months_since_last_raise),
               coalesce(c.p, parent.p, g.p),
               t.cell || ' · ' || t.sector
        FROM test t
        CROSS JOIN g
        LEFT JOIN cell_rates c ON c.cell = t.cell AND c.sector = t.sector
        LEFT JOIN parent ON parent.cell = t.cell;
        """
    )


def evaluate(con: duckdb.DuckDBPyConnection) -> dict[str, dict[str, float]]:
    """Metrics per model for the rows in `scored`.

    Ties are broken by hash(cik), not cik. CIKs are assigned in registration
    order, so sorting by them would quietly rank older registrants first.
    """
    topk = ", ".join(f"avg(y) FILTER (WHERE rn <= {k}) AS p_at_{k}" for k in TOP_K)
    rows = con.execute(
        f"""
        WITH r0 AS (
            SELECT
                *,
                row_number() OVER (PARTITION BY model ORDER BY score DESC, hash(cik)) AS rn,
                row_number() OVER (PARTITION BY model ORDER BY score, hash(cik)) AS rn_asc
            FROM scored
        ), r AS (
            -- Tied scores share their average rank (Mann-Whitney AUC).
            SELECT *, avg(rn_asc) OVER (PARTITION BY model, score) AS rank_asc FROM r0
        ), ap AS (
            SELECT model, rn, y,
                   sum(y) OVER (PARTITION BY model ORDER BY rn) / rn AS prec_at_rn
            FROM r
        )
        SELECT
            r.model,
            count(*)                                                    AS n,
            avg(r.y)                                                    AS base_rate,
            (sum(r.rank_asc) FILTER (WHERE r.y = 1)
                - sum(r.y) * (sum(r.y) + 1) / 2.0)
                / (sum(r.y) * (count(*) - sum(r.y)))                    AS auc,
            {topk},
            avg(power(r.prob - r.y, 2))                                 AS brier,
            any_value(apm.ap)                                           AS ap
        FROM r
        JOIN (SELECT model, avg(prec_at_rn) FILTER (WHERE y = 1) AS ap FROM ap GROUP BY model)
            AS apm USING (model)
        GROUP BY r.model
        """
    ).fetchall()
    cols = ["model", "n", "base_rate", "auc", *(f"p_at_{k}" for k in TOP_K), "brier", "ap"]
    return {r[0]: dict(zip(cols[1:], r[1:], strict=True)) for r in rows}


@dataclass
class BacktestResult:
    label: str
    horizon: int
    test_dates: list[dt.date]
    by_date: dict[dt.date, dict[str, dict[str, float]]] = field(default_factory=dict)
    importance: list[tuple[str, float]] = field(default_factory=list)


def run(
    con: duckdb.DuckDBPyConnection,
    *,
    label: str = "next_round",
    horizon: int = 18,
    first_snapshot: dt.date = dt.date(2011, 1, 1),
    first_test: dt.date = dt.date(2016, 1, 1),
) -> BacktestResult:
    if label not in LABELS:
        raise ValueError(f"label must be one of {LABELS}")
    features.build(con)
    end = data_end(con)
    last_test = max(
        d for d in snapshot_dates(first_test, end, 12) if months_after(d, horizon) <= end
    )
    dates = snapshot_dates(first_snapshot, last_test, 6)
    build_rows(con, dates, horizon)

    tests = snapshot_dates(first_test, last_test, 12)
    result = BacktestResult(label, horizon, tests)
    for t in tests:
        fit_and_score(
            con,
            "bt_rows",
            label,
            train_where=f"as_of + to_months({horizon}) <= DATE '{t}'",
            test_where=f"as_of = DATE '{t}'",
        )
        if gbm.available():
            result.importance = gbm.fit_and_score(con)  # keeps the latest test date's
        result.by_date[t] = evaluate(con)
    return result


def score_latest(
    con: duckdb.DuckDBPyConnection,
    *,
    label: str = "next_round",
    horizon: int = 18,
    top: int = 25,
    model: str | None = None,
) -> tuple[str, list[tuple]]:
    """Score every company in today's universe with a model trained on all
    snapshots whose outcomes are already known. Uses `gbm` when installed."""
    model = model or ("gbm" if gbm.available() else "cell")
    features.build(con)
    end = data_end(con)
    train_dates = [
        d for d in snapshot_dates(dt.date(2011, 1, 1), end, 6) if months_after(d, horizon) <= end
    ]
    build_rows(con, [*train_dates, end], horizon, table="score_rows")
    fit_and_score(
        con,
        "score_rows",
        label,
        train_where=f"as_of + to_months({horizon}) <= DATE '{end}'",
        test_where=f"as_of = DATE '{end}'",
    )
    if model == "gbm":
        gbm.fit_and_score(con)
    rows = con.execute(
        """
        SELECT as_of, cik, entity_name, sector, prob, reason
        FROM scored WHERE model = ?
        ORDER BY score DESC, hash(cik)
        LIMIT ?
        """,
        [model, top],
    ).fetchall()
    return model, rows


def _pct(x: float | None) -> str:
    return "–" if x is None else f"{100 * x:.1f}%"


def _num(x: float | None, digits: int = 3) -> str:
    return "–" if x is None else f"{x:.{digits}f}"


def render_markdown(result: BacktestResult) -> str:
    label_text = {
        "next_round": "start a **new round** and report new money",
        "raised_again": "report **any new money** (new round or more closings of an open one)",
        "went_public": "**go public** (priced IPO prospectus or first periodic report)",
    }[result.label]
    lines = [
        f"# Backtest: `{result.label}` within {result.horizon} months",
        "",
        "Generated by `investup backtest`. Don't edit by hand.",
        "",
        f"**Question:** given everything public on date T, which private venture-sector "
        f"companies (raised in the prior {ACTIVE_MONTHS} months) {label_text} within "
        f"{result.horizon} months?",
        "",
        "**Method:** walk-forward. For each test date T, models are trained only on "
        f"semi-annual snapshots whose {result.horizon}-month outcome window had closed by T. "
        "Features come from `features(as_of, ...)`, which only sees filings public by "
        "the snapshot date.",
        "",
        "## Summary (mean over test dates)",
        "",
        "| Model | AUC | Avg precision | P@100 | P@500 | P@1000 | Lift@100 | Brier |",
        "|---|---|---|---|---|---|---|---|",
    ]
    present = [m for m in models() if m in result.by_date[result.test_dates[0]]]
    for model in present:
        vals = [result.by_date[t][model] for t in result.test_dates]

        def mean(key: str, vals=vals) -> float | None:
            xs = [v[key] for v in vals if v[key] is not None]
            return sum(xs) / len(xs) if xs else None

        base = mean("base_rate")
        p100 = mean("p_at_100")
        lift = p100 / base if (p100 is not None and base) else None
        lines.append(
            f"| `{model}` | {_num(mean('auc'))} | {_num(mean('ap'))} | {_pct(p100)} | "
            f"{_pct(mean('p_at_500'))} | {_pct(mean('p_at_1000'))} | "
            f"{_num(lift, 2)}x | {_num(mean('brier'))} |"
        )
    lines += [
        "",
        "## By test date",
        "",
        "| Test date | Companies | Base rate | Model | AUC | P@100 | P@1000 | Brier |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for t in result.test_dates:
        for model in present:
            v = result.by_date[t][model]
            lines.append(
                f"| {t} | {v['n']:,} | {_pct(v['base_rate'])} | `{model}` | {_num(v['auc'])} | "
                f"{_pct(v['p_at_100'])} | {_pct(v['p_at_1000'])} | {_num(v['brier'])} |"
            )
    if result.importance:
        lines += [
            "",
            f"## What drives the `gbm` model (test date {result.test_dates[-1]})",
            "",
            "Mean absolute SHAP contribution (log-odds) per feature.",
            "",
            "| Feature | Mean \\|SHAP\\| |",
            "|---|---|",
            *(f"| {name} | {value:.3f} |" for name, value in result.importance),
        ]
    lines += [
        "",
        "## How to read this",
        "",
        "- **Base rate** is the share of the universe with the outcome. P@k is the share "
        "of the top-k ranked companies with the outcome. Lift@100 = P@100 / base rate.",
        "- **AUC** 0.5 = random, 1.0 = perfect ranking. **Brier** (lower is better) only "
        "applies to models that output probabilities.",
        "- Form D covers US companies that file. Some well-known companies raise "
        'through structures that don\'t file under their own name, and "raised" means '
        "*reported to the SEC*.",
    ]
    return "\n".join(lines) + "\n"


def write_report(result: BacktestResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(result))
