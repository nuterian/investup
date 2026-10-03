"""EDGAR quarterly master indexes: dated company milestones.

Every EDGAR filing appears in a quarterly master index (CIK, form type, date).
We keep only the form types that mark something about the company itself:

* ``periodic``: 10-K / 10-Q / 20-F / 40-F. The company reports publicly.
* ``ipo_registration``: S-1 / F-1 / SB-2.
* ``ipo_prospectus``: 424B4 / 424B1. The final prospectus of a priced offering.
* ``investment_company``: N-series, 485BPOS, 497 and similar. Mutual funds,
  insurance separate accounts and so on, which also file Form D.
* ``crowdfunding``: Form C and its updates.
* ``reg_a``: Regulation A offerings (1-A, 1-K).

Each milestone keeps its filing date, so "was this company public on date X"
can be answered without looking ahead. Form D CIKs are EDGAR CIKs, so the two
sources join directly.
"""

from __future__ import annotations

import gzip
import re
import tempfile
from pathlib import Path

import duckdb

from investup.sec import get, quarter_range

MASTER_URL = "https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/master.gz"
_LABEL_RE = re.compile(r"(\d{4})q([1-4])")

PERIODIC = {"10-K", "10-K405", "10-KSB", "10-KT", "10-Q", "10-QSB", "10-QT", "20-F", "40-F"}
IPO_REGISTRATION = {"S-1", "F-1", "SB-2"}
IPO_PROSPECTUS = {"424B4", "424B1"}
INVESTMENT_COMPANY_EXACT = {"485BPOS", "485APOS", "497", "497K", "24F-2NT"}
CROWDFUNDING = {"C", "C-U", "C-AR", "C-TR"}
REG_A = {"1-A", "1-K"}


def classify(form_type: str) -> str | None:
    """Map an EDGAR form type to a milestone category, or None to drop it."""
    base = form_type.strip().upper()
    if base.endswith("/A"):
        base = base[:-2]
    if base in PERIODIC:
        return "periodic"
    if base in IPO_REGISTRATION:
        return "ipo_registration"
    if base in IPO_PROSPECTUS:
        return "ipo_prospectus"
    if (
        base in INVESTMENT_COMPANY_EXACT
        or base.startswith("N-")
        or base.startswith("NSAR")
        or base.startswith("NPORT")
    ):
        return "investment_company"
    if base in CROWDFUNDING:
        return "crowdfunding"
    if base in REG_A:
        return "reg_a"
    return None


def parse_master(lines) -> list[tuple[str, str, str, str, str]]:
    """Return (cik, form_type, category, date_filed, filename) for milestone forms only."""
    rows = []
    for line in lines:
        parts = line.rstrip("\n").split("|")
        if len(parts) != 5 or not parts[0].isdigit():
            continue  # header, separator or blank line
        cik, _name, form_type, date_filed, filename = parts
        category = classify(form_type)
        if category is not None:
            rows.append((cik, form_type.strip(), category, date_filed, filename.strip()))
    return rows


def ensure_staging(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS stg_edgar_index (
            cik BIGINT NOT NULL,
            form_type VARCHAR NOT NULL,
            category VARCHAR NOT NULL,
            date_filed DATE NOT NULL,
            filename VARCHAR,
            source_quarter VARCHAR NOT NULL
        )
        """
    )


def download_range(
    start: tuple[int, int], end: tuple[int, int], dest: Path, *, force: bool = False
) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    paths = []
    for year, quarter in quarter_range(start, end):
        target = dest / f"{year}q{quarter}_master.gz"
        if target.exists() and not force:
            paths.append(target)
            continue
        tmp = target.with_suffix(".part")
        tmp.write_bytes(get(MASTER_URL.format(year=year, quarter=quarter)))
        tmp.replace(target)
        print(f"{year}q{quarter}: {target} ({target.stat().st_size / 1e6:.1f} MB)")
        paths.append(target)
    return paths


def load_file(con: duckdb.DuckDBPyConnection, path: Path) -> int:
    ensure_staging(con)
    m = _LABEL_RE.search(path.name)
    if not m:
        raise ValueError(f"Can't tell which quarter {path.name} is (expected 2015q1_master.gz)")
    quarter = f"{m.group(1)}q{m.group(2)}"

    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="latin-1") as f:
        rows = parse_master(f)

    with tempfile.NamedTemporaryFile("w", suffix=".tsv", delete=False) as tmp:
        tmp.writelines("\t".join(r) + "\n" for r in rows)
        tmp_path = tmp.name
    try:
        con.execute("BEGIN TRANSACTION")
        con.execute("DELETE FROM stg_edgar_index WHERE source_quarter = ?", [quarter])
        if rows:
            con.execute(
                """
                INSERT INTO stg_edgar_index
                SELECT cik, form_type, category, date_filed, filename, ? AS source_quarter
                FROM read_csv(?, delim='\t', header=false, quote='', escape='',
                    columns={'cik': 'BIGINT', 'form_type': 'VARCHAR', 'category': 'VARCHAR',
                             'date_filed': 'DATE', 'filename': 'VARCHAR'})
                """,
                [quarter, tmp_path],
            )
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return len(rows)


def load_dir(con: duckdb.DuckDBPyConnection, src: Path) -> None:
    files = sorted(src.glob("*_master.gz"))
    if not files:
        raise FileNotFoundError(f"No *_master.gz files in {src}")
    for path in files:
        print(f"{path.name}: {load_file(con, path):,} milestone filings")
