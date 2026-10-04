"""Column mapping for the SEC Form D data set TSV files.

Each quarterly ZIP contains one TSV per table (FORMDSUBMISSION, ISSUERS,
OFFERING, RELATEDPERSONS, ...). We map the SEC's upper-case headers onto our own
snake_case names. Each canonical column lists every header spelling we accept, so
a renamed column fails loudly (required) or becomes NULL with a warning
(optional) instead of silently loading garbage.

Primary names were checked against the real 2024Q1 data set. Each quarterly ZIP
also includes FormD_readme.html and FormD_metadata.json, the SEC's own field
reference. Aliases cover spellings seen in older quarters or the XML schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class SchemaError(ValueError):
    """A required column could not be found in a source file."""


@dataclass(frozen=True)
class Column:
    name: str
    aliases: tuple[str, ...]
    required: bool = False


@dataclass(frozen=True)
class TableSpec:
    name: str
    file_stem: str
    columns: tuple[Column, ...] = field(default_factory=tuple)

    def resolve(self, available: list[str]) -> dict[str, str | None]:
        """Map each canonical column to the matching source header (or None)."""
        by_upper = {c.upper(): c for c in available}
        mapping: dict[str, str | None] = {}
        missing_required = []
        for col in self.columns:
            source = next((by_upper[a] for a in col.aliases if a in by_upper), None)
            if source is None and col.required:
                missing_required.append(f"{col.name} (tried {', '.join(col.aliases)})")
            mapping[col.name] = source
        if missing_required:
            raise SchemaError(
                f"{self.file_stem}: missing required column(s): {'; '.join(missing_required)}. "
                f"Available columns: {', '.join(available)}"
            )
        return mapping


def _c(name: str, *aliases: str, required: bool = False) -> Column:
    return Column(name, aliases or (name.upper(),), required)


SUBMISSION = TableSpec(
    name="submission",
    file_stem="FORMDSUBMISSION",
    columns=(
        _c("accession_number", "ACCESSIONNUMBER", required=True),
        _c("file_num", "FILE_NUM", "FILENUM"),
        _c("filing_date", "FILING_DATE", "FILINGDATE", required=True),
        _c("sic_code", "SIC_CODE", "SICCODE"),
        _c("submission_type", "SUBMISSIONTYPE", "SUBMISSION_TYPE", required=True),
        _c("test_or_live", "TESTORLIVE"),
    ),
)

ISSUER = TableSpec(
    name="issuer",
    file_stem="ISSUERS",
    columns=(
        _c("accession_number", "ACCESSIONNUMBER", required=True),
        _c("is_primary", "IS_PRIMARYISSUER_FLAG", "ISPRIMARYISSUER", required=True),
        _c("cik", "CIK", required=True),
        _c("entity_name", "ENTITYNAME", "ISSUERNAME", required=True),
        _c("city", "CITY"),
        _c("state", "STATEORCOUNTRY"),
        _c("zip_code", "ZIPCODE"),
        _c("jurisdiction", "JURISDICTIONOFINC"),
        _c("entity_type", "ENTITYTYPE"),
        _c("year_of_inc_choice", "YEAROFINC_TIMESPAN_CHOICE"),
        _c("year_of_inc", "YEAROFINC_VALUE_ENTERED", "YEAROFINC_VALUE"),
    ),
)

OFFERING = TableSpec(
    name="offering",
    file_stem="OFFERING",
    columns=(
        _c("accession_number", "ACCESSIONNUMBER", required=True),
        _c("industry_group", "INDUSTRYGROUPTYPE", required=True),
        _c("investment_fund_type", "INVESTMENTFUNDTYPE"),
        _c("revenue_range", "REVENUERANGE"),
        _c("federal_exemptions", "FEDERALEXEMPTIONS_ITEMS_LIST"),
        _c("is_amendment", "ISAMENDMENT"),
        _c("previous_accession_number", "PREVIOUSACCESSIONNUMBER"),
        _c("first_sale_date", "SALE_DATE", "DATEOFFIRSTSALE", "DATEOFFIRSTSALE_VALUE"),
        _c("first_sale_yet_to_occur", "YETTOOCCUR"),
        _c("more_than_one_year", "MORETHANONEYEAR"),
        _c("is_equity", "ISEQUITYTYPE"),
        _c("is_debt", "ISDEBTTYPE"),
        _c("is_pooled_fund", "ISPOOLEDINVESTMENTFUNDTYPE"),
        _c("is_business_combination", "ISBUSINESSCOMBINATIONTRANS"),
        _c("minimum_investment", "MINIMUMINVESTMENTACCEPTED"),
        _c("total_offering_amount", "TOTALOFFERINGAMOUNT", required=True),
        _c("total_amount_sold", "TOTALAMOUNTSOLD", required=True),
        _c("total_remaining", "TOTALREMAINING"),
        _c("has_non_accredited", "HASNONACCREDITEDINVESTORS"),
        _c("total_investors", "TOTALNUMBERALREADYINVESTED"),
    ),
)

RELATED_PERSON = TableSpec(
    name="related_person",
    file_stem="RELATEDPERSONS",
    columns=(
        _c("accession_number", "ACCESSIONNUMBER", required=True),
        _c("first_name", "FIRSTNAME"),
        _c("middle_name", "MIDDLENAME"),
        _c("last_name", "LASTNAME", required=True),
        _c("city", "CITY"),
        _c("state", "STATEORCOUNTRY"),
        _c("relationship_1", "RELATIONSHIP_1"),
        _c("relationship_2", "RELATIONSHIP_2"),
        _c("relationship_3", "RELATIONSHIP_3"),
    ),
)

TABLES: tuple[TableSpec, ...] = (SUBMISSION, ISSUER, OFFERING, RELATED_PERSON)
