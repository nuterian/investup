"""Load Form D quarterly ZIPs into DuckDB staging tables.

Staging tables (`stg_formd_<table>`) keep every value as VARCHAR exactly as the SEC
published it, tagged with the source quarter. Type conversion and business logic
live in SQL views (see investup.ledger), so a parsing fix never needs a re-download.
Re-loading a quarter replaces that quarter's rows.
"""

from __future__ import annotations

import re
import tempfile
import zipfile
from pathlib import Path

import duckdb

from investup.formd.schema import TABLES, SchemaError, TableSpec

OPTIONAL_TABLES = {"related_person"}
_QUARTER_IN_NAME = re.compile(r"(\d{4})[qQ]([1-4])")


def staging_table(spec: TableSpec) -> str:
    return f"stg_formd_{spec.name}"


def ensure_staging(con: duckdb.DuckDBPyConnection) -> None:
    for spec in TABLES:
        cols = ", ".join(f"{c.name} VARCHAR" for c in spec.columns)
        con.execute(
            f"CREATE TABLE IF NOT EXISTS {staging_table(spec)} "
            f"({cols}, source_quarter VARCHAR NOT NULL)"
        )


def quarter_label(path: Path) -> str:
    m = _QUARTER_IN_NAME.search(path.name)
    if not m:
        raise ValueError(f"Can't tell which quarter {path.name} is (expected e.g. 2015q1_d.zip)")
    return f"{m.group(1)}q{m.group(2)}"


def _find_member(zf: zipfile.ZipFile, stem: str) -> str | None:
    for name in zf.namelist():
        base = Path(name).name.upper()
        if base in (f"{stem}.TSV", f"{stem}.TXT"):
            return name
    return None


def _read_tsv(con: duckdb.DuckDBPyConnection, path: Path) -> None:
    """Read a TSV into the temp table `raw`, all columns as VARCHAR."""
    con.execute("DROP TABLE IF EXISTS raw")
    last_error: Exception | None = None
    for encoding in ("utf-8", "latin-1"):
        try:
            con.execute(
                "CREATE TEMP TABLE raw AS SELECT * FROM read_csv(?, delim='\t', header=true, "
                "all_varchar=true, quote='', escape='', null_padding=true, encoding=?)",
                [str(path), encoding],
            )
            return
        except duckdb.InvalidInputException as e:
            last_error = e
    raise last_error  # type: ignore[misc]


def load_zip(con: duckdb.DuckDBPyConnection, zip_path: Path) -> dict[str, int]:
    """Load one quarterly ZIP. Returns row counts per table."""
    ensure_staging(con)
    quarter = quarter_label(zip_path)
    counts: dict[str, int] = {}

    with zipfile.ZipFile(zip_path) as zf, tempfile.TemporaryDirectory() as tmp:
        con.execute("BEGIN TRANSACTION")
        try:
            for spec in TABLES:
                member = _find_member(zf, spec.file_stem)
                if member is None:
                    if spec.name in OPTIONAL_TABLES:
                        print(f"{quarter}: warning: no {spec.file_stem}.tsv, skipping")
                        continue
                    raise SchemaError(f"{zip_path.name}: no {spec.file_stem}.tsv in archive")

                extracted = Path(zf.extract(member, tmp))
                _read_tsv(con, extracted)
                available = [r[0] for r in con.execute("DESCRIBE raw").fetchall()]
                mapping = spec.resolve(available)
                for col, source in mapping.items():
                    if source is None:
                        print(f"{quarter}: warning: {spec.file_stem} has no column for {col}")

                select = ", ".join(
                    f"NULLIF(TRIM(\"{src}\"), '') AS {col}" if src else f"NULL AS {col}"
                    for col, src in mapping.items()
                )
                table = staging_table(spec)
                con.execute(f"DELETE FROM {table} WHERE source_quarter = ?", [quarter])
                con.execute(f"INSERT INTO {table} SELECT {select}, ? FROM raw", [quarter])
                counts[spec.name] = con.execute(
                    f"SELECT count(*) FROM {table} WHERE source_quarter = ?", [quarter]
                ).fetchone()[0]
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    return counts


def load_dir(con: duckdb.DuckDBPyConnection, src: Path) -> None:
    zips = sorted(src.glob("*.zip"))
    if not zips:
        raise FileNotFoundError(f"No .zip files in {src}")
    for path in zips:
        counts = load_zip(con, path)
        summary = ", ".join(f"{k}={v:,}" for k, v in counts.items())
        print(f"{quarter_label(path)}: {summary}")
