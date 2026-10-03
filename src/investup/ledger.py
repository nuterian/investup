"""The funding ledger: typed, point-in-time views over the Form D staging tables.

Every fact has two dates:

* ``known_at``: the day the SEC published the filing. This is when the fact
  became public.
* ``event_date``: the best estimate of when the money moved (date of first sale,
  falling back to ``known_at``).

Anything used as a model feature must filter on ``known_at <= as_of``. The
``company_snapshot(as_of)`` macro does this. It is the guard against the
look-ahead bias that broke the 2015 model (docs/AUDIT_AND_ROADMAP.md, M2).
"""

from __future__ import annotations

import duckdb

from investup.formd.load import ensure_staging

LEDGER_SQL = r"""
CREATE OR REPLACE MACRO is_true(x) AS upper(coalesce(x, '')) IN ('Y', 'YES', 'TRUE', 'T', '1');

CREATE OR REPLACE MACRO parse_date(x) AS CAST(coalesce(
    try_strptime(x, '%Y-%m-%d'),
    try_strptime(x, '%d-%b-%Y'),
    try_strptime(x, '%m/%d/%Y')
) AS DATE);

-- Amounts arrive as text: '1000000', '1,000,000', '$1,000,000.00' or 'Indefinite'.
CREATE OR REPLACE MACRO parse_amount(x) AS
    try_cast(regexp_replace(x, '[$,\s]', '', 'g') AS DOUBLE);

-- One row per Form D filing, joined to its primary issuer and offering.
-- A filing can show up in more than one quarterly file; keep the latest copy.
CREATE OR REPLACE VIEW formd_filing AS
WITH s AS (
    SELECT DISTINCT ON (accession_number) * FROM stg_formd_submission
    ORDER BY accession_number, source_quarter DESC
), i AS (
    SELECT DISTINCT ON (accession_number) * FROM stg_formd_issuer
    WHERE is_true(is_primary)
    ORDER BY accession_number, source_quarter DESC
), o AS (
    SELECT DISTINCT ON (accession_number) * FROM stg_formd_offering
    ORDER BY accession_number, source_quarter DESC
)
SELECT
    s.accession_number,
    try_cast(i.cik AS BIGINT)                                    AS cik,
    i.entity_name,
    i.city,
    i.state,
    i.entity_type,
    i.jurisdiction,
    try_cast(i.year_of_inc AS INTEGER)                           AS year_of_inc,
    s.file_num,
    s.submission_type,
    upper(coalesce(s.submission_type, '')) LIKE 'D/A%' OR is_true(o.is_amendment)
                                                                 AS is_amendment,
    parse_date(s.filing_date)                                    AS known_at,
    parse_date(o.first_sale_date)                                AS first_sale_date,
    o.industry_group,
    o.investment_fund_type,
    o.revenue_range,
    o.federal_exemptions,
    is_true(o.is_equity)                                         AS is_equity,
    is_true(o.is_debt)                                           AS is_debt,
    is_true(o.is_pooled_fund)
        OR o.industry_group ILIKE 'pooled investment fund%'
        OR o.investment_fund_type IS NOT NULL                    AS is_pooled_fund,
    is_true(o.is_business_combination)                           AS is_business_combination,
    parse_amount(o.total_offering_amount)                        AS total_offering_amount,
    upper(coalesce(o.total_offering_amount, '')) LIKE 'INDEF%'   AS offering_indefinite,
    parse_amount(o.total_amount_sold)                            AS total_amount_sold,
    try_cast(o.total_investors AS INTEGER)                       AS total_investors,
    s.source_quarter
FROM s
JOIN i USING (accession_number)
JOIN o USING (accession_number);

-- Raises by operating companies. Investment funds (VC/PE/hedge funds also file
-- Form D) and business-combination filings are excluded.
--
-- An offering and its amendments share a file number. Amendments report the
-- cumulative amount sold, so new money = the increase over the previous filing
-- in the same chain. That uses only earlier filings, so it doesn't leak.
CREATE OR REPLACE VIEW raise_event AS
WITH ops AS (
    SELECT *, coalesce(file_num, accession_number) AS offering_key
    FROM formd_filing
    WHERE NOT is_pooled_fund
      AND NOT is_business_combination
      AND cik IS NOT NULL
      AND known_at IS NOT NULL
), chained AS (
    SELECT
        *,
        row_number() OVER w                                      AS filing_seq,
        lag(total_amount_sold) OVER w                            AS prev_amount_sold
    FROM ops
    WINDOW w AS (PARTITION BY cik, offering_key ORDER BY known_at, accession_number)
)
SELECT
    accession_number,
    cik,
    entity_name,
    state,
    industry_group,
    offering_key,
    filing_seq,
    filing_seq = 1                                               AS is_new_offering,
    known_at,
    CASE
        WHEN filing_seq = 1 AND first_sale_date <= known_at THEN first_sale_date
        ELSE known_at
    END                                                          AS event_date,
    year_of_inc,
    total_offering_amount,
    total_amount_sold,
    greatest(coalesce(total_amount_sold, 0) - coalesce(prev_amount_sold, 0), 0)
                                                                 AS new_money,
    total_investors,
    revenue_range,
    source_quarter
FROM chained;

-- What was publicly known about every company on `as_of`.
CREATE OR REPLACE MACRO company_snapshot(as_of) AS TABLE
WITH visible AS (
    SELECT *, CAST(as_of AS DATE) AS snapshot_date
    FROM raise_event
    WHERE known_at <= CAST(as_of AS DATE)
), agg AS (
    SELECT
        cik,
        any_value(snapshot_date)                                 AS snapshot_date,
        arg_max(entity_name, known_at)                           AS entity_name,
        arg_max(state, known_at)                                 AS state,
        mode(industry_group)                                     AS industry_group,
        min(year_of_inc)                                         AS year_of_inc,
        min(known_at)                                            AS first_filing_at,
        max(known_at) FILTER (WHERE new_money > 0)               AS last_raise_at,
        count(*) FILTER (WHERE is_new_offering)                  AS n_offerings,
        sum(new_money)                                           AS total_raised,
        coalesce(sum(new_money) FILTER (
            WHERE known_at > snapshot_date - INTERVAL 24 MONTH), 0)
                                                                 AS raised_last_24m,
        max(total_investors)                                     AS max_investors
    FROM visible
    GROUP BY cik
)
SELECT
    * EXCLUDE (snapshot_date),
    date_diff('month', last_raise_at, snapshot_date)             AS months_since_last_raise
FROM agg;

-- Phase 2 label: did the company publicly report new money in (as_of, as_of + horizon]?
CREATE OR REPLACE MACRO raised_again_label(as_of, horizon_months) AS TABLE
WITH win AS (
    SELECT
        CAST(as_of AS DATE)                                      AS start_date,
        CAST(as_of AS DATE) + to_months(CAST(horizon_months AS INTEGER)) AS end_date
), future AS (
    SELECT DISTINCT r.cik
    FROM raise_event AS r, win
    WHERE r.new_money > 0 AND r.known_at > win.start_date AND r.known_at <= win.end_date
)
SELECT
    snap.cik,
    future.cik IS NOT NULL                                       AS raised_again
FROM company_snapshot(as_of) AS snap
LEFT JOIN future USING (cik);
"""


def build(con: duckdb.DuckDBPyConnection) -> None:
    ensure_staging(con)
    con.execute(LEDGER_SQL)


def stats(con: duckdb.DuckDBPyConnection) -> list[tuple]:
    return con.execute(
        """
        SELECT
            year(known_at)                                   AS year,
            count(*)                                         AS filings,
            count(*) FILTER (WHERE is_new_offering)          AS new_offerings,
            count(DISTINCT cik)                              AS companies,
            round(sum(new_money) / 1e9, 2)                   AS new_money_bn
        FROM raise_event
        GROUP BY 1 ORDER BY 1
        """
    ).fetchall()
