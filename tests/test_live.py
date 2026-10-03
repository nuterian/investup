from __future__ import annotations

import gzip
from pathlib import Path

from conftest import filing, write_quarter_zip
from investup import ledger
from investup.formd import live, load

HEADER = """<SEC-DOCUMENT>{acc}.txt : {date}
<SEC-HEADER>{acc}.hdr.sgml : {date}
ACCESSION NUMBER:\t\t{acc}
CONFORMED SUBMISSION TYPE:\t{form}
FILED AS OF DATE:\t\t{date}

FILER:

\tCOMPANY DATA:\t
\t\tCOMPANY CONFORMED NAME:\t\t\tCO-ISSUER LLC
\t\tCENTRAL INDEX KEY:\t\t\t0000009999

\tFILING VALUES:
\t\tFORM TYPE:\t\t{form}
\t\tSEC FILE NUMBER:\t021-000001

FILER:

\tCOMPANY DATA:\t
\t\tCOMPANY CONFORMED NAME:\t\t\t{name}
\t\tCENTRAL INDEX KEY:\t\t\t{cik:010d}

\tFILING VALUES:
\t\tFORM TYPE:\t\t{form}
\t\tSEC FILE NUMBER:\t{file_num}
</SEC-HEADER>
<DOCUMENT>
<TYPE>{form}
<FILENAME>primary_doc.xml
<TEXT>
<XML>
<?xml version="1.0"?>
<edgarSubmission>
  <submissionType>{form}</submissionType>
  <testOrLive>LIVE</testOrLive>
  <primaryIssuer>
    <cik>{cik:010d}</cik>
    <entityName>{name}</entityName>
    <issuerAddress><city>Austin</city><stateOrCountry>TX</stateOrCountry></issuerAddress>
    <entityType>Corporation</entityType>
    <yearOfInc><withinFiveYears>true</withinFiveYears><value>2024</value></yearOfInc>
  </primaryIssuer>
  <relatedPersonsList>
    <relatedPersonInfo>
      <relatedPersonName><firstName>Grace</firstName><lastName>Hopper</lastName></relatedPersonName>
      <relatedPersonAddress><city>Austin</city><stateOrCountry>TX</stateOrCountry></relatedPersonAddress>
      <relatedPersonRelationshipList>
        <relationship>Executive Officer</relationship><relationship>Director</relationship>
      </relatedPersonRelationshipList>
    </relatedPersonInfo>
  </relatedPersonsList>
  <offeringData>
    <industryGroup><industryGroupType>Other Technology</industryGroupType></industryGroup>
    <issuerSize><revenueRange>No Revenues</revenueRange></issuerSize>
    <federalExemptionsExclusions><item>06b</item></federalExemptionsExclusions>
    <typeOfFiling>
      <newOrAmendment><isAmendment>{amend}</isAmendment></newOrAmendment>
      <dateOfFirstSale><value>{first_sale}</value></dateOfFirstSale>
    </typeOfFiling>
    <typesOfSecuritiesOffered><isEquityType>true</isEquityType></typesOfSecuritiesOffered>
    <businessCombinationTransaction>
      <isBusinessCombinationTransaction>false</isBusinessCombinationTransaction>
    </businessCombinationTransaction>
    <offeringSalesAmounts>
      <totalOfferingAmount>{offered}</totalOfferingAmount>
      <totalAmountSold>{sold}</totalAmountSold>
    </offeringSalesAmounts>
    <investors><totalNumberAlreadyInvested>7</totalNumberAlreadyInvested></investors>
  </offeringData>
</edgarSubmission>
</XML>
</TEXT>
</DOCUMENT>
</SEC-DOCUMENT>
"""


def submission(acc, cik, name, date, sold, *, form="D", file_num="021-424242", offered="9000000"):
    return HEADER.format(
        acc=acc,
        cik=cik,
        name=name,
        date=date.replace("-", ""),
        form=form,
        file_num=file_num,
        amend="true" if form == "D/A" else "false",
        first_sale=date,
        offered=offered,
        sold=sold,
    )


def write_index(edgar_dir: Path, quarter: str, rows: list[tuple[int, str, str, str]]) -> None:
    edgar_dir.mkdir(parents=True, exist_ok=True)
    body = "CIK|Company Name|Form Type|Date Filed|Filename\n" + "-" * 20 + "\n"
    body += "".join(
        f"{cik}|x|{form}|{date}|edgar/data/{cik}/{acc}.txt\n" for cik, form, date, acc in rows
    )
    with gzip.open(edgar_dir / f"{quarter}_master.gz", "wt") as f:
        f.write(body)


def cache(live_dir: Path, quarter: str, acc: str, text: str) -> None:
    path = live.cache_path(live_dir, quarter, acc)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(text.encode()))


def test_parse_submission_uses_primary_issuers_file_number():
    rows = live.parse_submission(
        submission("0000000001-26-000001", 7007, "Nova Labs Inc", "2026-08-03", "1500000")
    )
    assert rows["submission"][0]["file_num"] == "021-424242"
    assert rows["submission"][0]["filing_date"] == "2026-08-03"
    assert rows["issuer"][0]["state"] == "TX"
    assert rows["issuer"][0]["year_of_inc"] == "2024"
    assert rows["issuer"][0]["year_of_inc_choice"] == "withinFiveYears"
    assert rows["offering"][0]["total_amount_sold"] == "1500000"
    assert rows["offering"][0]["federal_exemptions"] == "06b"
    person = rows["related_person"][0]
    assert (person["last_name"], person["relationship_1"], person["relationship_2"]) == (
        "Hopper",
        "Executive Officer",
        "Director",
    )


def test_live_quarters_are_those_after_the_last_data_set(tmp_path):
    formd_dir, edgar_dir = tmp_path / "formd", tmp_path / "edgar"
    formd_dir.mkdir()
    write_quarter_zip(formd_dir, "2026q2", [filing("a", "1", "A", "2026-05-01", "1", file_num="f")])
    for q in ("2026q2", "2026q3", "2026q4"):
        write_index(edgar_dir, q, [])
    assert live.live_quarters(formd_dir, edgar_dir) == ["2026q3", "2026q4"]


def test_live_rows_flow_into_the_ledger_and_yield_to_official_data(con, tmp_path):
    formd_dir, edgar_dir, live_dir = tmp_path / "formd", tmp_path / "edgar", tmp_path / "live"
    formd_dir.mkdir()
    write_quarter_zip(
        formd_dir,
        "2026q2",
        [
            filing(
                "0007-26-1", "7007", "Nova Labs Inc", "2026-05-01", "1000000", file_num="021-424242"
            )
        ],
    )
    write_index(edgar_dir, "2026q3", [(7007, "D/A", "2026-08-03", "0000000001-26-000001")])
    cache(
        live_dir,
        "2026q3",
        "0000000001-26-000001",
        submission(
            "0000000001-26-000001", 7007, "Nova Labs Inc", "2026-08-03", "2500000", form="D/A"
        ),
    )
    load.load_dir(con, formd_dir)
    counts = live.load(con, formd_dir, edgar_dir, live_dir)
    assert counts["submission"] == 1
    ledger.build(con)

    # The live amendment continues the official offering: $1.5M of new money.
    rows = con.execute(
        "SELECT source_quarter, new_money FROM raise_event WHERE cik = 7007 ORDER BY known_at"
    ).fetchall()
    assert rows == [("2026q2", 1_000_000), ("live-2026q3", 1_500_000)]

    # Once the official 2026q3 data set exists, live rows for that quarter go away.
    write_quarter_zip(
        formd_dir,
        "2026q3",
        [
            filing(
                "0000000001-26-000001",
                "7007",
                "Nova Labs Inc",
                "2026-08-03",
                "2500000",
                file_num="021-424242",
                sub_type="D/A",
            )
        ],
    )
    load.load_dir(con, formd_dir)
    live.load(con, formd_dir, edgar_dir, live_dir)
    assert (
        con.execute(
            "SELECT count(*) FROM stg_formd_submission WHERE source_quarter LIKE 'live-%'"
        ).fetchone()[0]
        == 0
    )
    assert (
        con.execute(
            "SELECT source_quarter FROM raise_event WHERE accession_number = '0000000001-26-000001'"
        ).fetchone()[0]
        == "2026q3"
    )


def test_fetch_only_downloads_missing_filings(monkeypatch, tmp_path):
    formd_dir, edgar_dir, live_dir = tmp_path / "formd", tmp_path / "edgar", tmp_path / "live"
    formd_dir.mkdir()
    write_quarter_zip(formd_dir, "2026q2", [filing("a", "1", "A", "2026-05-01", "1", file_num="f")])
    write_index(
        edgar_dir,
        "2026q3",
        [
            (1, "D", "2026-08-01", "acc-1"),
            (2, "D", "2026-08-02", "acc-2"),
            (3, "8-K", "2026-08-02", "x"),
        ],
    )
    cache(live_dir, "2026q3", "acc-1", "already here")
    requested = []
    monkeypatch.setattr(live, "get", lambda url, delay=0: requested.append(url) or b"filing")
    assert live.fetch(formd_dir, edgar_dir, live_dir) == 1
    assert requested == ["https://www.sec.gov/Archives/edgar/data/2/acc-2.txt"]


def test_rate_limiter_spaces_requests(monkeypatch):
    clock = [100.0]
    slept = []
    monkeypatch.setattr(live.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(live.time, "sleep", lambda s: slept.append(round(s, 3)))
    limiter = live.RateLimiter(0.12)
    for _ in range(3):
        limiter.wait()
    assert slept == [0.0, 0.12, 0.24]
