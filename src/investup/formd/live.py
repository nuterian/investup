"""Form D filings since the last quarterly data set, straight from EDGAR.

The SEC publishes Form D data sets once a quarter, a few weeks after it ends,
but each filing is on EDGAR the day it's filed. This module fills the gap:

1. List Form D and D/A filings for the quarters after the latest data set,
   from EDGAR's quarterly master index (refreshed nightly for the current
   quarter; see investup.edgar).
2. Fetch each filing's full submission text once and cache it gzipped.
3. Parse the header (filing date, SEC file number) and the Form D XML into the
   same staging columns the data sets use, tagged ``live-<quarter>``.

Live rows are rebuilt from the cache on every load and are only kept for
quarters the official data sets don't cover yet, so the official data replaces
them as soon as it's published.
"""

from __future__ import annotations

import gzip
import re
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import duckdb

from investup.formd.load import ensure_staging, staging_table
from investup.formd.schema import TABLES
from investup.sec import get

ARCHIVES = "https://www.sec.gov/Archives/"
FORMS = {"D", "D/A"}
_QUARTER = re.compile(r"(\d{4})q([1-4])")
_REQUEST_GAP = 0.12  # seconds between request starts: under the SEC's 10/second
_WORKERS = 6  # parallel downloads; the rate limiter still caps the total


class RateLimiter:
    """Spaces request starts at least `gap` seconds apart across threads."""

    def __init__(self, gap: float):
        self.gap = gap
        self.lock = threading.Lock()
        self.next = 0.0

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            start = max(now, self.next)
            self.next = start + self.gap
        time.sleep(max(0.0, start - now))


# --- Which filings ------------------------------------------------------------


def official_quarters(formd_dir: Path) -> set[str]:
    """Quarters covered by downloaded official data sets, e.g. {'2026q2', ...}."""
    out = set()
    for p in formd_dir.glob("*_d.zip"):
        m = _QUARTER.search(p.name)
        if m:
            out.add(f"{m.group(1)}q{m.group(2)}")
    return out


def live_quarters(formd_dir: Path, edgar_dir: Path) -> list[str]:
    """Quarters with an EDGAR index but no official Form D data set yet."""
    official = official_quarters(formd_dir)
    if not official:
        return []
    last = max(official)
    indexed = set()
    for p in edgar_dir.glob("*_master.gz"):
        m = _QUARTER.search(p.name)
        if m:
            indexed.add(f"{m.group(1)}q{m.group(2)}")
    return sorted(q for q in indexed if q > last)


def index_entries(edgar_dir: Path, quarter: str) -> list[tuple[str, str, str, str]]:
    """(accession, form type, date filed, archive path) for Form D filings."""
    path = edgar_dir / f"{quarter}_master.gz"
    out = []
    with gzip.open(path, "rt", encoding="latin-1") as f:
        for line in f:
            parts = line.rstrip("\n").split("|")
            if len(parts) != 5 or parts[2] not in FORMS:
                continue
            filename = parts[4].strip()
            accession = Path(filename).stem
            out.append((accession, parts[2], parts[3], filename))
    return out


def cache_path(live_dir: Path, quarter: str, accession: str) -> Path:
    return live_dir / quarter / f"{accession}.txt.gz"


def fetch(
    formd_dir: Path,
    edgar_dir: Path,
    live_dir: Path,
    *,
    limit: int | None = None,
    workers: int = _WORKERS,
) -> int:
    """Download filings missing from the cache. Returns how many were fetched."""
    todo: list[tuple[str, str]] = []
    for quarter in live_quarters(formd_dir, edgar_dir):
        entries = index_entries(edgar_dir, quarter)
        missing = [
            (quarter, e) for e in entries if not cache_path(live_dir, quarter, e[0]).exists()
        ]
        print(f"{quarter}: {len(entries):,} Form D filings, {len(missing):,} to fetch")
        todo += [(q, e[3]) for q, e in missing]
    if limit is not None:
        todo = todo[:limit]

    limiter = RateLimiter(_REQUEST_GAP)
    done = 0
    lock = threading.Lock()

    def one(item: tuple[str, str]) -> None:
        nonlocal done
        quarter, filename = item
        for attempt in range(4):
            limiter.wait()
            try:
                data = get(ARCHIVES + filename, delay=0)
                break
            except OSError:  # network errors and HTTP 403/429/5xx (HTTPError)
                if attempt == 3:
                    raise
                time.sleep(2**attempt * 5)
        target = cache_path(live_dir, quarter, Path(filename).stem)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(f".{threading.get_ident()}.part")
        tmp.write_bytes(gzip.compress(data))
        tmp.replace(target)
        with lock:
            done += 1
            if done % 1000 == 0:
                print(f"  {done:,}/{len(todo):,}", flush=True)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for _ in pool.map(one, todo):
            pass
    return done


# --- Parsing ------------------------------------------------------------------


def _strip_ns(root: ET.Element) -> ET.Element:
    for el in root.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def _text(el: ET.Element | None, path: str) -> str | None:
    if el is None:
        return None
    found = el.find(path)
    if found is None or found.text is None:
        return None
    value = found.text.strip()
    return value or None


def _header(text: str) -> tuple[str | None, str | None, dict[str, str]]:
    """(accession, filed date YYYY-MM-DD, {cik: file number}) from the SGML header."""
    header = text.split("</SEC-HEADER>", 1)[0]
    acc = re.search(r"ACCESSION NUMBER:\s*(\S+)", header)
    filed = re.search(r"FILED AS OF DATE:\s*(\d{8})", header)
    file_nums: dict[str, str] = {}
    for block in re.split(r"\n\s*FILER:\s*\n", header)[1:]:
        cik = re.search(r"CENTRAL INDEX KEY:\s*(\d+)", block)
        num = re.search(r"SEC FILE NUMBER:\s*(\S+)", block)
        if cik and num:
            file_nums[str(int(cik.group(1)))] = num.group(1)
    date = filed.group(1) if filed else None
    return (
        acc.group(1) if acc else None,
        f"{date[:4]}-{date[4:6]}-{date[6:]}" if date else None,
        file_nums,
    )


def parse_submission(text: str) -> dict[str, list[dict[str, str | None]]]:
    """Rows for each staging table (keyed by TableSpec.name) from one filing."""
    accession, filed, file_nums = _header(text)
    m = re.search(r"<XML>\s*(.*?)\s*</XML>", text, re.S)
    if not accession or not m:
        return {}
    root = _strip_ns(ET.fromstring(m.group(1).encode("utf-8")))
    issuer = root.find("primaryIssuer")
    offering = root.find("offeringData")
    cik = _text(issuer, "cik")
    cik_key = str(int(cik)) if cik and cik.isdigit() else None

    year = issuer.find("yearOfInc") if issuer is not None else None
    choice = None
    if year is not None:
        for option in ("withinFiveYears", "overFiveYears", "yetToBeFormed"):
            if (_text(year, option) or "").lower() == "true":
                choice = option
    exemptions = (
        ",".join(
            i.text.strip() for i in offering.findall("federalExemptionsExclusions/item") if i.text
        )
        if offering is not None
        else None
    )
    revenue = _text(offering, "issuerSize/revenueRange") or _text(
        offering, "issuerSize/aggregateNetAssetValueRange"
    )

    rows: dict[str, list[dict[str, str | None]]] = {
        "submission": [
            {
                "accession_number": accession,
                "file_num": file_nums.get(cik_key or "") or next(iter(file_nums.values()), None),
                "filing_date": filed,
                "sic_code": None,
                "submission_type": _text(root, "submissionType"),
                "test_or_live": _text(root, "testOrLive"),
            }
        ],
        "issuer": [
            {
                "accession_number": accession,
                "is_primary": "YES",
                "cik": cik,
                "entity_name": _text(issuer, "entityName"),
                "city": _text(issuer, "issuerAddress/city"),
                "state": _text(issuer, "issuerAddress/stateOrCountry"),
                "zip_code": _text(issuer, "issuerAddress/zipCode"),
                "jurisdiction": _text(issuer, "jurisdictionOfInc"),
                "entity_type": _text(issuer, "entityType"),
                "year_of_inc_choice": choice,
                "year_of_inc": _text(year, "value"),
            }
        ],
        "offering": [
            {
                "accession_number": accession,
                "industry_group": _text(offering, "industryGroup/industryGroupType"),
                "investment_fund_type": _text(
                    offering, "industryGroup/investmentFundInfo/investmentFundType"
                ),
                "revenue_range": revenue,
                "federal_exemptions": exemptions,
                "is_amendment": _text(offering, "typeOfFiling/newOrAmendment/isAmendment"),
                "previous_accession_number": _text(
                    offering, "typeOfFiling/newOrAmendment/previousAccessionNumber"
                ),
                "first_sale_date": _text(offering, "typeOfFiling/dateOfFirstSale/value"),
                "first_sale_yet_to_occur": _text(
                    offering, "typeOfFiling/dateOfFirstSale/yetToOccur"
                ),
                "more_than_one_year": _text(offering, "durationOfOffering/moreThanOneYear"),
                "is_equity": _text(offering, "typesOfSecuritiesOffered/isEquityType"),
                "is_debt": _text(offering, "typesOfSecuritiesOffered/isDebtType"),
                "is_pooled_fund": _text(
                    offering, "typesOfSecuritiesOffered/isPooledInvestmentFundType"
                ),
                "is_business_combination": _text(
                    offering, "businessCombinationTransaction/isBusinessCombinationTransaction"
                ),
                "minimum_investment": _text(offering, "minimumInvestmentAccepted"),
                "total_offering_amount": _text(
                    offering, "offeringSalesAmounts/totalOfferingAmount"
                ),
                "total_amount_sold": _text(offering, "offeringSalesAmounts/totalAmountSold"),
                "total_remaining": _text(offering, "offeringSalesAmounts/totalRemaining"),
                "has_non_accredited": _text(offering, "investors/hasNonAccreditedInvestors"),
                "total_investors": _text(offering, "investors/totalNumberAlreadyInvested"),
            }
        ],
        "related_person": [],
    }
    for person in root.findall("relatedPersonsList/relatedPersonInfo"):
        roles = [
            r.text.strip()
            for r in person.findall("relatedPersonRelationshipList/relationship")
            if r.text
        ]
        rows["related_person"].append(
            {
                "accession_number": accession,
                "first_name": _text(person, "relatedPersonName/firstName"),
                "middle_name": _text(person, "relatedPersonName/middleName"),
                "last_name": _text(person, "relatedPersonName/lastName"),
                "city": _text(person, "relatedPersonAddress/city"),
                "state": _text(person, "relatedPersonAddress/stateOrCountry"),
                "relationship_1": roles[0] if len(roles) > 0 else None,
                "relationship_2": roles[1] if len(roles) > 1 else None,
                "relationship_3": roles[2] if len(roles) > 2 else None,
            }
        )
    return rows


# --- Loading ------------------------------------------------------------------


def _clean(v: str | None) -> str:
    return "" if v is None else re.sub(r"[\t\r\n]+", " ", v)


def load(con: duckdb.DuckDBPyConnection, formd_dir: Path, edgar_dir: Path, live_dir: Path) -> dict:
    """Replace all live rows with those parsed from the cache. Returns row counts."""
    ensure_staging(con)
    quarters = live_quarters(formd_dir, edgar_dir)
    rows: dict[str, list[dict]] = {spec.name: [] for spec in TABLES}
    failed = 0
    for quarter in quarters:
        for path in sorted((live_dir / quarter).glob("*.txt.gz")):
            try:
                parsed = parse_submission(
                    gzip.decompress(path.read_bytes()).decode("utf-8", "replace")
                )
            except ET.ParseError:
                failed += 1
                continue
            for name, table_rows in parsed.items():
                for r in table_rows:
                    r["source_quarter"] = f"live-{quarter}"
                rows[name].extend(table_rows)

    con.execute("BEGIN TRANSACTION")
    try:
        for spec in TABLES:
            table = staging_table(spec)
            con.execute(f"DELETE FROM {table} WHERE source_quarter LIKE 'live-%'")
            data = rows[spec.name]
            if not data:
                continue
            cols = [c.name for c in spec.columns] + ["source_quarter"]
            with tempfile.NamedTemporaryFile(
                "w", suffix=".tsv", delete=False, encoding="utf-8"
            ) as f:
                for r in data:
                    f.write("\t".join(_clean(r.get(c)) for c in cols) + "\n")
                tmp = f.name
            try:
                types = ", ".join(f"'{c}': 'VARCHAR'" for c in cols)
                con.execute(
                    f"""
                    INSERT INTO {table} BY NAME
                    SELECT * REPLACE ({", ".join(f"NULLIF({c}, '') AS {c}" for c in cols)})
                    FROM read_csv(?, delim='\t', header=false, quote='', escape='',
                                  columns={{{types}}})
                    """,
                    [tmp],
                )
            finally:
                Path(tmp).unlink(missing_ok=True)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    counts = {name: len(v) for name, v in rows.items()}
    counts["unparseable"] = failed
    return counts
