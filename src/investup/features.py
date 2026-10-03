"""Point-in-time model features.

``features(as_of, active_months)`` returns one row per company in
``venture_universe(as_of, active_months)``. Every input is limited to filings
public on or before ``as_of`` (the ledger's ``known_at`` rule), so these rows
can be scored as of any historical date without look-ahead.
"""

from __future__ import annotations

import duckdb

from investup import ledger

FEATURES_SQL = r"""
-- People (executives, directors, promoters) named on each company's raises.
-- A person is identified by name + state. That's noisy for common names; the
-- features macro ignores people linked to too many companies, which also drops
-- placement agents and fund administrators.
CREATE OR REPLACE VIEW person_company AS
SELECT
    upper(trim(p.first_name)) || ' ' || upper(trim(p.last_name)) || '|'
        || coalesce(upper(trim(p.state)), '')                    AS person_key,
    r.cik,
    min(r.known_at)                                              AS first_seen_at
FROM stg_formd_related_person AS p
JOIN raise_event AS r USING (accession_number)
WHERE length(trim(coalesce(p.first_name, ''))) > 1
  AND length(trim(coalesce(p.last_name, ''))) > 1
GROUP BY ALL;

CREATE OR REPLACE MACRO features(as_of, active_months) AS TABLE
WITH u AS (
    SELECT * FROM venture_universe(as_of, active_months)
), pc AS (
    SELECT * FROM person_company WHERE first_seen_at <= CAST(as_of AS DATE)
), person_degree AS (
    SELECT person_key, count(DISTINCT cik) AS n_companies FROM pc GROUP BY person_key
), pc_clean AS (
    SELECT pc.* FROM pc JOIN person_degree USING (person_key) WHERE n_companies <= 20
), team AS (
    SELECT u.cik, count(DISTINCT pc_clean.person_key) AS n_people
    FROM u JOIN pc_clean ON pc_clean.cik = u.cik
    GROUP BY u.cik
), track AS (
    SELECT
        mine.cik,
        count(DISTINCT other.cik)                                AS team_prior_companies,
        count(DISTINCT other.cik) FILTER (
            WHERE m.went_public_at <= CAST(as_of AS DATE))       AS team_prior_public_companies
    FROM u
    JOIN pc_clean AS mine ON mine.cik = u.cik
    JOIN pc_clean AS other
      ON other.person_key = mine.person_key
     AND other.cik <> mine.cik
     AND other.first_seen_at < mine.first_seen_at
    LEFT JOIN edgar_milestone AS m ON m.cik = other.cik
    GROUP BY mine.cik
), recent AS (
    SELECT *, CAST(as_of AS DATE) AS d
    FROM raise_event
    WHERE new_money > 0
      AND NOT is_suspect_amount
      AND known_at <= CAST(as_of AS DATE)
      AND known_at > CAST(as_of AS DATE) - INTERVAL 24 MONTH
), sector_heat AS (
    SELECT
        sector,
        count(*) FILTER (WHERE known_at > d - INTERVAL 12 MONTH) AS raises_12m,
        count(*) FILTER (WHERE known_at <= d - INTERVAL 12 MONTH) AS raises_prev_12m
    FROM recent
    GROUP BY sector
)
SELECT
    CAST(as_of AS DATE)                                          AS as_of,
    u.cik,
    u.entity_name,
    u.sector,
    u.industry_group,
    u.state,
    u.months_since_last_raise,
    u.months_since_first_filing,
    year(CAST(as_of AS DATE)) - u.year_of_inc                    AS age_years,
    u.n_offerings,
    u.n_raises_last_24m,
    ln(1 + u.total_raised)                                       AS log_total_raised,
    ln(1 + u.raised_last_12m)                                    AS log_raised_last_12m,
    ln(1 + u.raised_last_24m)                                    AS log_raised_last_24m,
    ln(1 + coalesce(u.last_raise_amount, 0))                     AS log_last_raise_amount,
    u.last_total_investors,
    u.max_investors,
    coalesce(u.last_offering_indefinite OR u.last_offering_remaining > 0, false)
                                                                 AS last_offering_open,
    u.last_revenue_range,
    u.has_crowdfunded,
    u.has_filed_ipo_registration,
    coalesce(team.n_people, 0)                                   AS n_people,
    coalesce(track.team_prior_companies, 0)                      AS team_prior_companies,
    coalesce(track.team_prior_public_companies, 0)               AS team_prior_public_companies,
    (coalesce(sh.raises_12m, 0) + 1.0) / (coalesce(sh.raises_prev_12m, 0) + 1.0)
                                                                 AS sector_heat,
    percent_rank() OVER (PARTITION BY u.sector ORDER BY u.raised_last_24m)
                                                                 AS raised_24m_pct_in_sector
FROM u
LEFT JOIN team USING (cik)
LEFT JOIN track USING (cik)
LEFT JOIN sector_heat AS sh USING (sector);

-- Features joined to every outcome label we track.
CREATE OR REPLACE MACRO labeled_features(as_of, active_months, horizon_months) AS TABLE
SELECT
    f.*,
    nr.next_round,
    ra.raised_again,
    wp.went_public
FROM features(as_of, active_months) AS f
JOIN next_round_label(as_of, horizon_months) AS nr USING (cik)
JOIN raised_again_label(as_of, horizon_months) AS ra USING (cik)
JOIN went_public_label(as_of, horizon_months) AS wp USING (cik);
"""


def build(con: duckdb.DuckDBPyConnection) -> None:
    ledger.build(con)
    con.execute(FEATURES_SQL)
