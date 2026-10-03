"""Command-line entry point: `investup <command>`."""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

from investup import ledger
from investup.formd import download, load

DEFAULT_DB = Path("data/investup.duckdb")
DEFAULT_RAW = Path("data/raw/formd")


def _connect(path: Path) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path))


def cmd_download(args: argparse.Namespace) -> None:
    start = download.parse_quarter(args.start)
    end = download.parse_quarter(args.end) if args.end else download.last_complete_quarter()
    download.download_range(start, end, args.dest, force=args.force)


def cmd_load(args: argparse.Namespace) -> None:
    con = _connect(args.db)
    load.load_dir(con, args.src)
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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="investup")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("download", help="Download SEC Form D quarterly data sets")
    p.add_argument("--start", default="2008q1", help="First quarter, e.g. 2015q1")
    p.add_argument("--end", help="Last quarter (default: last complete quarter)")
    p.add_argument("--dest", type=Path, default=DEFAULT_RAW)
    p.add_argument("--force", action="store_true", help="Re-download existing files")
    p.set_defaults(func=cmd_download)

    p = sub.add_parser("load", help="Load downloaded ZIPs into DuckDB and build the ledger")
    p.add_argument("--src", type=Path, default=DEFAULT_RAW)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.set_defaults(func=cmd_load)

    p = sub.add_parser("stats", help="Print yearly ledger coverage")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.set_defaults(func=cmd_stats)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
