"""Command-line entry point: `investup <command>`."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import duckdb

from investup import backtest, digest, edgar, export, ledger, sec
from investup.formd import download, load

DEFAULT_DB = Path("data/investup.duckdb")
DEFAULT_RAW = Path("data/raw")
SOURCES = ("formd", "edgar")


def _connect(path: Path) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path))


def cmd_download(args: argparse.Namespace) -> None:
    start = sec.parse_quarter(args.start)
    end = sec.parse_quarter(args.end) if args.end else sec.last_complete_quarter()
    if args.source in ("formd", "all"):
        download.download_range(start, end, args.raw / "formd", force=args.force)
    if args.source in ("edgar", "all"):
        edgar.download_range(start, end, args.raw / "edgar", force=args.force)


def cmd_load(args: argparse.Namespace) -> None:
    con = _connect(args.db)
    if args.source in ("formd", "all"):
        load.load_dir(con, args.raw / "formd")
    if args.source in ("edgar", "all"):
        edgar.load_dir(con, args.raw / "edgar")
    ledger.build(con)


def cmd_stats(args: argparse.Namespace) -> None:
    con = _connect(args.db)
    ledger.build(con)
    print(
        f"{'year':>6} {'filings':>9} {'new offerings':>14} {'companies':>10} {'new $bn':>9}"
        f" {'venture cos':>12} {'venture $bn':>12}"
    )
    for year, filings, offerings, companies, money, v_cos, v_money in ledger.stats(con):
        print(
            f"{year!s:>6} {filings:>9,} {offerings:>14,} {companies:>10,} {money or 0:>9,.2f}"
            f" {v_cos:>12,} {v_money or 0:>12,.2f}"
        )


def cmd_backtest(args: argparse.Namespace) -> None:
    con = _connect(args.db)
    result = backtest.run(con, label=args.label, horizon=args.horizon)
    out = args.out or Path("docs/backtests") / f"{args.label}.md"
    backtest.write_report(result, out)
    print(backtest.render_markdown(result).split("## By test date")[0].rstrip())
    print(f"\nFull report: {out}")


def cmd_score(args: argparse.Namespace) -> None:
    con = _connect(args.db)
    model, rows = backtest.score_latest(
        con, label=args.label, horizon=args.horizon, top=args.top, model=args.model
    )
    if not rows:
        print("No companies to score.")
        return
    print(
        f"Scored as of {rows[0][0]} with `{model}`: P({args.label} within {args.horizon} months)\n"
    )
    for _as_of, cik, name, sector, prob, reason in rows:
        print(f"{prob:6.1%}  {name[:40]:<40} {sector:<12} CIK {cik}")
        print(f"        {reason}")


def cmd_digest(args: argparse.Namespace) -> None:
    con = _connect(args.db)
    since = dt.date.fromisoformat(args.since) if args.since else None
    d = digest.build(con, since=since, top=args.top)
    out = args.out or Path("docs/digests") / f"{d.end}.md"
    digest.write(d, out)
    print(f"{d.universe_filers:,} companies filed between {d.since} and {d.end}.")
    for _cik, name, _state, sector, _filed, _money, p_step, p_ipo, *_ in d.step_up[:10]:
        p_ipo_text = "  –  " if p_ipo is None else f"{p_ipo:5.1%}"
        print(f"  bigger round {p_step:5.1%} · IPO {p_ipo_text}  {name[:45]} ({sector})")
    print(f"\nFull digest: {out}")


def cmd_export(args: argparse.Namespace) -> None:
    con = _connect(args.db)
    sizes = export.export(con, args.out, model=args.model, shards=args.shards)
    for name, size in sizes.items():
        print(f"{name:<14} {size / 1e6:8.2f} MB")
    print(f"\nSite data written to {args.out}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="investup")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("download", help="Download Form D data sets and EDGAR indexes")
    p.add_argument("--source", choices=(*SOURCES, "all"), default="all")
    p.add_argument("--start", default="2008q1", help="First quarter, e.g. 2015q1")
    p.add_argument("--end", help="Last quarter (default: last complete quarter)")
    p.add_argument("--raw", type=Path, default=DEFAULT_RAW, help="Download directory")
    p.add_argument("--force", action="store_true", help="Re-download existing files")
    p.set_defaults(func=cmd_download)

    p = sub.add_parser("load", help="Load downloaded files into DuckDB and build the ledger")
    p.add_argument("--source", choices=(*SOURCES, "all"), default="all")
    p.add_argument("--raw", type=Path, default=DEFAULT_RAW, help="Download directory")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.set_defaults(func=cmd_load)

    p = sub.add_parser("stats", help="Print yearly ledger coverage")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("backtest", help="Walk-forward backtest; writes a markdown report")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--label", choices=backtest.LABELS, default="step_up")
    p.add_argument("--horizon", type=int, default=18, help="Outcome window in months")
    p.add_argument("--out", type=Path, help="Default: docs/backtests/<label>.md")
    p.set_defaults(func=cmd_backtest)

    p = sub.add_parser("score", help="Rank today's private companies, with reasons")
    p.add_argument("--model", choices=("gbm", "cell"), help="Default: gbm if installed")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--label", choices=backtest.LABELS, default="step_up")
    p.add_argument("--horizon", type=int, default=18)
    p.add_argument("--top", type=int, default=25)
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("digest", help="Recent filers ranked by bigger-round and IPO odds")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--since", help="Start of window, YYYY-MM-DD (default: 91 days before data end)")
    p.add_argument("--top", type=int, default=25)
    p.add_argument("--out", type=Path, help="Default: docs/digests/<data end>.md")
    p.set_defaults(func=cmd_digest)

    p = sub.add_parser("export", help="Write the JSON files the static site reads")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--out", type=Path, default=Path("site/public/data"))
    p.add_argument("--model", choices=("gbm", "cell"), help="Default: gbm if installed")
    p.add_argument("--shards", type=int, default=export.SHARDS, help="Company detail files")
    p.set_defaults(func=cmd_export)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
