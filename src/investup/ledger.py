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

from investup import edgar
from investup.formd.load import ensure_staging

LEDGER_SQL = r"""
CREATE OR REPLACE MACRO is_true(x) AS upper(coalesce(x, '')) IN ('Y', 'YES', 'TRUE', 'T', '1');

-- The SEC changed formats over time: '2014-06-30 16:26:21' before 2020Q3,
-- '30-SEP-2020' after it. Sale dates are '2014-06-16'.
CREATE OR REPLACE MACRO parse_date(x) AS CAST(coalesce(
    try_strptime(x, '%Y-%m-%d %H:%M:%S'),
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
    WHERE upper(coalesce(test_or_live, 'LIVE')) <> 'TEST'
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

-- Coarse sectors from the Form D industry groups. Venture sectors leave out
-- finance, insurance, real estate and extractive/utility businesses, which file
-- Form D for reasons unrelated to startup growth.
CREATE OR REPLACE MACRO sector(industry_group) AS CASE
    WHEN industry_group IN ('Computers', 'Telecommunications', 'Other Technology')
        THEN 'Technology'
    WHEN industry_group IN ('Biotechnology', 'Pharmaceuticals', 'Hospitals and Physicians',
                            'Health Insurance', 'Other Health Care')
        THEN 'Health Care'
    WHEN industry_group IN ('Energy Conservation', 'Environmental Services', 'Other Energy')
        THEN 'Energy'
    WHEN industry_group IN ('Oil and Gas', 'Coal Mining', 'Electric Utilities')
        THEN 'Extractive & Utilities'
    WHEN industry_group IN ('Commercial Banking', 'Insurance', 'Investing', 'Investment Banking',
                            'Pooled Investment Fund', 'Other Banking and Financial Services')
        THEN 'Financial Services'
    WHEN industry_group IN ('Commercial', 'Construction', 'REITS and Finance', 'Residential',
                            'Other Real Estate')
        THEN 'Real Estate'
    WHEN industry_group IN ('Retailing', 'Restaurants', 'Airlines and Airports',
                            'Lodging and Conventions', 'Tourism and Travel Services',
                            'Other Travel')
        THEN 'Consumer'
    WHEN industry_group IN ('Manufacturing', 'Agriculture') THEN 'Industrial'
    WHEN industry_group = 'Business Services' THEN 'Business Services'
    ELSE 'Other'
END;

-- Insurance separate accounts and LLC/LP "pools" file Form D under ordinary
-- industry codes without ticking the pooled-fund box. Catch them by name. The
-- pattern is deliberately narrow: broader ones also hit real startups (e.g.
-- "Gene Pool Technologies", "Information Assurance Corp").
CREATE OR REPLACE MACRO looks_like_investment_vehicle(name) AS regexp_matches(
    upper(coalesce(name, '')),
    '(SEPARATE ACCOUNT|VARIABLE (ACCOUNT|SERIES)|\bPOOL( [IVX0-9]+)?,? (LLC|L\.?P\.?)$)'
);

CREATE OR REPLACE MACRO is_venture_sector(s) AS
    s NOT IN ('Financial Services', 'Real Estate', 'Extractive & Utilities');

-- First date each company reached each EDGAR milestone (see investup.edgar).
CREATE OR REPLACE VIEW edgar_milestone AS
SELECT
    cik,
    min(date_filed) FILTER (WHERE category = 'periodic')           AS first_periodic_at,
    min(date_filed) FILTER (WHERE category = 'ipo_registration')   AS first_ipo_registration_at,
    min(date_filed) FILTER (WHERE category = 'ipo_prospectus')     AS first_ipo_prospectus_at,
    min(date_filed) FILTER (WHERE category = 'investment_company') AS first_investment_company_at,
    min(date_filed) FILTER (WHERE category = 'crowdfunding')       AS first_crowdfunding_at,
    min(date_filed) FILTER (WHERE category = 'reg_a')              AS first_reg_a_at,
    -- Went public: priced IPO or first periodic report (also covers SPACs and
    -- direct listings), whichever came first.
    least(min(date_filed) FILTER (WHERE category = 'periodic'),
          min(date_filed) FILTER (WHERE category = 'ipo_prospectus'))
                                                                   AS went_public_at
FROM stg_edgar_index
GROUP BY cik;

-- Raises by operating companies. Investment funds (VC/PE/hedge funds also file
-- Form D) and business-combination filings are excluded.
--
-- An offering and its amendments share a file number. Amendments report the
-- cumulative amount sold, so new money = the increase over the previous filing
-- in the same chain. That uses only earlier filings, so it doesn't leak.
--
-- Filers sometimes fix a typo with a same-day amendment (e.g. $104,999,999,994
-- corrected to $104,999,994). For each offering and day we keep only the last
-- filing. Amounts that still aren't plausible are flagged and left out of
-- company totals and labels.
CREATE OR REPLACE VIEW raise_event AS
WITH ops AS (
    SELECT *, coalesce(file_num, accession_number) AS offering_key
    FROM formd_filing
    WHERE NOT is_pooled_fund
      AND NOT is_business_combination
      AND cik IS NOT NULL
      AND known_at IS NOT NULL
    QUALIFY row_number() OVER (
        PARTITION BY cik, coalesce(file_num, accession_number), known_at
        ORDER BY accession_number DESC
    ) = 1
), chained AS (
    SELECT
        *,
        row_number() OVER w                                      AS filing_seq,
        lag(total_amount_sold) OVER w                            AS prev_amount_sold,
        min(known_at) OVER (PARTITION BY cik, offering_key)      AS offering_started_at
    FROM ops
    WINDOW w AS (PARTITION BY cik, offering_key ORDER BY known_at, accession_number)
)
SELECT
    accession_number,
    cik,
    entity_name,
    state,
    industry_group,
    sector(industry_group)                                       AS sector,
    offering_key,
    filing_seq,
    filing_seq = 1                                               AS is_new_offering,
    offering_started_at,
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
    (new_money >= 1e9 AND coalesce(total_investors, 0) <= 1) OR new_money >= 5e10
                                                                 AS is_suspect_amount,
    total_investors,
    revenue_range,
    total_offering_amount - total_amount_sold                    AS offering_remaining,
    offering_indefinite,
    -- Point-in-time EDGAR status of the issuer when this filing was made.
    coalesce(m.went_public_at <= known_at, false)                AS issuer_was_public,
    coalesce(m.first_investment_company_at <= known_at, false)
        OR looks_like_investment_vehicle(entity_name)            AS issuer_was_investment_company,
    source_quarter
FROM chained
LEFT JOIN edgar_milestone AS m USING (cik);

-- What was publicly known about every company on `as_of`.
CREATE OR REPLACE MACRO company_snapshot(as_of) AS TABLE
WITH visible AS (
    SELECT
        * REPLACE (CASE WHEN is_suspect_amount THEN 0 ELSE new_money END AS new_money),
        CAST(as_of AS DATE)                                      AS snapshot_date
    FROM raise_event
    WHERE known_at <= CAST(as_of AS DATE)
), agg AS (
    SELECT
        cik,
        any_value(snapshot_date)                                 AS snapshot_date,
        arg_max(entity_name, known_at)                           AS entity_name,
        arg_max(state, known_at)                                 AS state,
        mode(industry_group)                                     AS industry_group,
        sector(mode(industry_group))                             AS sector,
        is_venture_sector(sector(mode(industry_group)))          AS is_venture_sector,
        min(year_of_inc)                                         AS year_of_inc,
        min(known_at)                                            AS first_filing_at,
        max(known_at) FILTER (WHERE new_money > 0)               AS last_raise_at,
        count(*) FILTER (WHERE is_new_offering)                  AS n_offerings,
        sum(new_money)                                           AS total_raised,
        coalesce(sum(new_money) FILTER (
            WHERE known_at > snapshot_date - INTERVAL 24 MONTH), 0)
                                                                 AS raised_last_24m,
        coalesce(sum(new_money) FILTER (
            WHERE known_at > snapshot_date - INTERVAL 12 MONTH), 0)
                                                                 AS raised_last_12m,
        count(*) FILTER (
            WHERE new_money > 0 AND known_at > snapshot_date - INTERVAL 24 MONTH)
                                                                 AS n_raises_last_24m,
        arg_max(new_money, known_at) FILTER (WHERE new_money > 0) AS last_raise_amount,
        arg_max(total_investors, known_at)                       AS last_total_investors,
        max(total_investors)                                     AS max_investors,
        arg_max(revenue_range, known_at)                         AS last_revenue_range,
        arg_max(offering_remaining, known_at)                    AS last_offering_remaining,
        arg_max(offering_indefinite, known_at)                   AS last_offering_indefinite
    FROM visible
    GROUP BY cik
)
SELECT
    agg.* EXCLUDE (snapshot_date),
    date_diff('month', last_raise_at, snapshot_date)             AS months_since_last_raise,
    date_diff('month', first_filing_at, snapshot_date)           AS months_since_first_filing,
    coalesce(m.went_public_at <= snapshot_date, false)           AS is_public,
    coalesce(m.first_investment_company_at <= snapshot_date, false)
        OR looks_like_investment_vehicle(entity_name)            AS is_investment_company,
    coalesce(m.first_ipo_registration_at <= snapshot_date, false)
                                                                 AS has_filed_ipo_registration,
    coalesce(m.first_crowdfunding_at <= snapshot_date, false)    AS has_crowdfunded
FROM agg
LEFT JOIN edgar_milestone AS m USING (cik);

-- Private, venture-sector companies that raised within `active_months` of
-- `as_of`. This is the population the model scores.
CREATE OR REPLACE MACRO venture_universe(as_of, active_months) AS TABLE
SELECT *
FROM company_snapshot(as_of)
WHERE is_venture_sector
  AND NOT is_public
  AND NOT is_investment_company
  AND months_since_last_raise <= active_months;

-- Phase 2 label: did the company publicly report new money in (as_of, as_of + horizon]?
CREATE OR REPLACE MACRO raised_again_label(as_of, horizon_months) AS TABLE
WITH win AS (
    SELECT
        CAST(as_of AS DATE)                                      AS start_date,
        CAST(as_of AS DATE) + to_months(CAST(horizon_months AS INTEGER)) AS end_date
), future AS (
    SELECT DISTINCT r.cik
    FROM raise_event AS r, win
    WHERE r.new_money > 0 AND NOT r.is_suspect_amount
      AND r.known_at > win.start_date AND r.known_at <= win.end_date
)
SELECT
    snap.cik,
    future.cik IS NOT NULL                                       AS raised_again
FROM company_snapshot(as_of) AS snap
LEFT JOIN future USING (cik);

-- Stricter label: new money from an offering that *started* after `as_of`,
-- i.e. a new round, not more closings of the round already open.
CREATE OR REPLACE MACRO next_round_label(as_of, horizon_months) AS TABLE
WITH win AS (
    SELECT
        CAST(as_of AS DATE)                                      AS start_date,
        CAST(as_of AS DATE) + to_months(CAST(horizon_months AS INTEGER)) AS end_date
), future AS (
    SELECT DISTINCT r.cik
    FROM raise_event AS r, win
    WHERE r.new_money > 0 AND NOT r.is_suspect_amount
      AND r.offering_started_at > win.start_date
      AND r.known_at <= win.end_date
)
SELECT
    snap.cik,
    future.cik IS NOT NULL                                       AS next_round
FROM company_snapshot(as_of) AS snap
LEFT JOIN future USING (cik);

-- Exit label: the company went public (IPO prospectus or first periodic report)
-- in (as_of, as_of + horizon].
CREATE OR REPLACE MACRO went_public_label(as_of, horizon_months) AS TABLE
SELECT
    snap.cik,
    coalesce(
        m.went_public_at > CAST(as_of AS DATE)
        AND m.went_public_at <= CAST(as_of AS DATE) + to_months(CAST(horizon_months AS INTEGER)),
        false
    )                                                            AS went_public
FROM company_snapshot(as_of) AS snap
LEFT JOIN edgar_milestone AS m USING (cik);
"""


def build(con: duckdb.DuckDBPyConnection) -> None:
    ensure_staging(con)
    edgar.ensure_staging(con)
    con.execute(LEDGER_SQL)


def stats(con: duckdb.DuckDBPyConnection) -> list[tuple]:
    return con.execute(
        """
        SELECT
            year(known_at)                                   AS year,
            count(*)                                         AS filings,
            count(*) FILTER (WHERE is_new_offering)          AS new_offerings,
            count(DISTINCT cik)                              AS companies,
            round(sum(new_money) FILTER (WHERE NOT is_suspect_amount) / 1e9, 2)
                                                             AS new_money_bn,
            count(DISTINCT cik) FILTER (WHERE venture)               AS venture_companies,
            round(sum(new_money) FILTER (WHERE venture AND NOT is_suspect_amount) / 1e9, 2)
                                                             AS venture_money_bn
        FROM (
            SELECT
                *,
                is_venture_sector(sector)
                    AND NOT issuer_was_public
                    AND NOT issuer_was_investment_company    AS venture
            FROM raise_event
        )
        GROUP BY 1 ORDER BY 1
        """
    ).fetchall()
