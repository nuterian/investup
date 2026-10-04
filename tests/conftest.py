"""Synthetic Form D quarterly ZIPs for tests.

These are built from the documented SEC column names, not copied from a real
download. They test our parsing and ledger logic, not the SEC's actual format.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import duckdb
import pytest

SUBMISSION_COLS = [
    "ACCESSIONNUMBER",
    "FILE_NUM",
    "FILING_DATE",
    "SIC_CODE",
    "SUBMISSIONTYPE",
    "TESTORLIVE",
]
ISSUER_COLS = [
    "ACCESSIONNUMBER",
    "IS_PRIMARYISSUER_FLAG",
    "ISSUER_SEQ_KEY",
    "CIK",
    "ENTITYNAME",
    "CITY",
    "STATEORCOUNTRY",
    "ZIPCODE",
    "JURISDICTIONOFINC",
    "ENTITYTYPE",
    "YEAROFINC_TIMESPAN_CHOICE",
    "YEAROFINC_VALUE_ENTERED",
]
OFFERING_COLS = [
    "ACCESSIONNUMBER",
    "INDUSTRYGROUPTYPE",
    "INVESTMENTFUNDTYPE",
    "REVENUERANGE",
    "FEDERALEXEMPTIONS_ITEMS_LIST",
    "ISAMENDMENT",
    "PREVIOUSACCESSIONNUMBER",
    "SALE_DATE",
    "YETTOOCCUR",
    "MORETHANONEYEAR",
    "ISEQUITYTYPE",
    "ISDEBTTYPE",
    "ISPOOLEDINVESTMENTFUNDTYPE",
    "ISBUSINESSCOMBINATIONTRANS",
    "MINIMUMINVESTMENTACCEPTED",
    "TOTALOFFERINGAMOUNT",
    "TOTALAMOUNTSOLD",
    "TOTALREMAINING",
    "HASNONACCREDITEDINVESTORS",
    "TOTALNUMBERALREADYINVESTED",
]
PERSON_COLS = [
    "ACCESSIONNUMBER",
    "RELATEDPERSON_SEQ_KEY",
    "FIRSTNAME",
    "MIDDLENAME",
    "LASTNAME",
    "CITY",
    "STATEORCOUNTRY",
    "RELATIONSHIP_1",
    "RELATIONSHIP_2",
    "RELATIONSHIP_3",
]


def filing(
    acc: str,
    cik: str,
    name: str,
    filed: str,
    sold: str,
    *,
    file_num: str,
    sub_type: str = "D",
    offered: str = "10000000",
    first_sale: str = "",
    industry: str = "Other Technology",
    fund_type: str = "",
    investors: str = "5",
    test: bool = False,
) -> dict:
    is_amendment = "true" if sub_type == "D/A" else "false"
    pooled = "true" if fund_type else "false"
    return {
        "submission": [acc, file_num, filed, "", sub_type, "TEST" if test else "LIVE"],
        "issuers": [
            [
                acc,
                "YES",
                "1",
                cik,
                name,
                "San Francisco",
                "CA",
                "94107",
                "DELAWARE",
                "Corporation",
                "withinFiveYears",
                "2015",
            ],
        ],
        "offering": [
            acc,
            industry,
            fund_type,
            "Decline to Disclose",
            "06b",
            is_amendment,
            "",
            first_sale,
            "",
            "false",
            "true",
            "false",
            pooled,
            "false",
            "0",
            offered,
            sold,
            "",
            "false",
            investors,
        ],
        "persons": [
            [
                acc,
                "1",
                "Ada",
                "",
                "Lovelace",
                "San Francisco",
                "CA",
                "Executive Officer",
                "Director",
                "",
            ]
        ],
    }


def write_quarter_zip(dest: Path, quarter: str, filings: list[dict], *, offering_cols=None) -> Path:
    offering_cols = offering_cols or OFFERING_COLS

    def tsv(cols, rows):
        return "\n".join(["\t".join(cols)] + ["\t".join(r) for r in rows]) + "\n"

    sub_rows = [f["submission"] for f in filings]
    iss_rows = [r for f in filings for r in f["issuers"]]
    off_rows = [f["offering"] for f in filings]
    per_rows = [r for f in filings for r in f["persons"]]

    path = dest / f"{quarter}_d.zip"
    with zipfile.ZipFile(path, "w") as zf:
        folder = f"{quarter.upper()}_d/"
        zf.writestr(folder + "FORMDSUBMISSION.tsv", tsv(SUBMISSION_COLS, sub_rows))
        zf.writestr(folder + "ISSUERS.tsv", tsv(ISSUER_COLS, iss_rows))
        zf.writestr(folder + "OFFERING.tsv", tsv(offering_cols, off_rows))
        zf.writestr(folder + "RELATEDPERSONS.tsv", tsv(PERSON_COLS, per_rows))
    return path


@pytest.fixture
def con():
    c = duckdb.connect()
    yield c
    c.close()


@pytest.fixture
def sample_quarters(tmp_path: Path) -> Path:
    """A small history:

    * Acme Robotics raises $2M (2016), adds $1.5M to the same offering in an
      amendment (2017), then opens a new $5M offering (2019).
    * Beta Bio files a notice in 2016 but sells nothing.
    * Gamma Ventures Fund is a VC fund and must be excluded.
    """
    acme_1 = filing(
        "0001-16-000001",
        "1001",
        "Acme Robotics Inc",
        "2016-03-01",
        "2000000",
        file_num="021-1",
        first_sale="2016-02-15",
    )
    # Acme's 2016 filing also lists a non-primary co-issuer, which must be ignored.
    acme_1["issuers"].append(
        [
            "0001-16-000001",
            "N",
            "2",
            "9999",
            "Acme Holdings LLC",
            "Austin",
            "TX",
            "",
            "",
            "",
            "",
            "",
        ]
    )
    beta = filing(
        "0003-16-000001",
        "3003",
        "Beta Bio Inc",
        "2016-05-10 14:02:11",
        "0",
        file_num="021-3",
        offered="1000000",
        industry="Biotechnology",
    )
    fund = filing(
        "0002-16-000001",
        "2002",
        "Gamma Ventures Fund I LP",
        "2016-04-01",
        "50000000",
        file_num="021-2",
        industry="Pooled Investment Fund",
        fund_type="Venture Capital Fund",
    )
    acme_amend = filing(
        "0001-17-000001",
        "1001",
        "Acme Robotics Inc",
        "2017-02-20",
        "3,500,000",
        file_num="021-1",
        sub_type="D/A",
    )
    acme_2 = filing(
        "0001-19-000001",
        "1001",
        "Acme Robotics, Inc.",
        "01-JUN-2019",
        "$5,000,000",
        file_num="021-9",
        first_sale="2019-05-20",
        investors="12",
    )

    write_quarter_zip(tmp_path, "2016q1", [acme_1])
    write_quarter_zip(tmp_path, "2016q2", [beta, fund])
    write_quarter_zip(tmp_path, "2017q1", [acme_amend])
    write_quarter_zip(tmp_path, "2019q2", [acme_2])
    return tmp_path
