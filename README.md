# Investup

An open, explainable early-signal engine for private companies, built entirely from
public records.

Investup tracks every US company that reports a private raise to the SEC (Form D).
It shows how fast each company is moving compared with its peers, and (soon) estimates
the chance it raises again in the next 18 months, with the reasons behind every number.

> **Status: rebuilding.** This started as a 2015 class project built on Crunchbase data.
> [`docs/AUDIT_AND_ROADMAP.md`](docs/AUDIT_AND_ROADMAP.md) explains why it's being rebuilt
> and what the plan is. Right now we're in Phase 1: the open funding ledger (Form D 2008–2026 loads end to end).

## Principles

- **Open data only.** Every number traces back to a public filing. No scraped or licensed
  vendor data.
- **Point-in-time.** Every fact records when it became public (`known_at`). Features and
  backtests only use what was known on the date they're computed for.
- **Honest evaluation.** Time-split backtests, calibrated probabilities and published
  results, not "90% accuracy".

## Quick start

Needs Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra model   # --extra model adds LightGBM; leave it out for the DuckDB-only models

# The SEC requires a contact in the User-Agent for automated downloads.
export INVESTUP_USER_AGENT="Your Name you@example.com"

uv run investup download   # Form D data sets + EDGAR indexes, 2008 to now (~430 MB)
uv run investup load       # -> data/investup.duckdb (~2 minutes)
uv run investup stats      # yearly coverage summary
uv run investup backtest   # walk-forward backtest -> docs/backtests/<label>.md
uv run investup score      # rank today's private companies, with reasons
uv run investup digest     # recent filers ranked by bigger-round and IPO odds -> docs/digests/
```

The downloader finds each quarter's ZIP by reading the SEC's
[Form D data sets page](https://www.sec.gov/data-research/sec-markets-data/form-d-data-sets).
If that page moves, set `INVESTUP_FORMD_INDEX_URL`, or download the ZIPs by hand into
`data/raw/formd/`. The full history (2008 to now) is about 190 MB and takes about a minute
to download and about a minute to load.

### Querying the ledger

```bash
uv run python -c "import duckdb; c = duckdb.connect('data/investup.duckdb'); \
  print(c.sql(\"SELECT * FROM company_snapshot(DATE '2020-01-01') ORDER BY raised_last_24m DESC LIMIT 20\"))"
```

| Object | What it is |
|---|---|
| `stg_formd_*` | Raw SEC rows, all text, tagged with `source_quarter` |
| `formd_filing` | One typed row per filing: primary issuer joined to the offering |
| `raise_event` | Operating-company raises (investment funds excluded), with `new_money` derived from amendment chains, a coarse `sector`, and an `is_suspect_amount` flag for implausible filer-reported amounts |
| `company_snapshot(as_of)` | What was publicly known about each company on `as_of`. Filter on `is_venture_sector` to drop finance, real estate and extractive companies |
| `edgar_milestone` | First date each CIK filed a periodic report, an S-1/F-1, an IPO prospectus, fund forms, Form C or Reg A |
| `venture_universe(as_of, months)` | The population we score: private, US, venture-sector, not a fund/SPV/LLP, raised within N months |
| `features(as_of, months)` | Point-in-time model features, including the team's track record from Form D related persons |
| `step_up_label`, `next_round_label`, `raised_again_label`, `went_public_label` `(as_of, months)` | Outcomes in the N months after `as_of` |

## Results so far

Walk-forward backtests over test years 2016–2024. Each year's model only sees outcomes
known by that date. Full tables, per-year results, feature importance and calibration
are in [`docs/backtests/`](docs/backtests/).

| Question | Base rate | Baseline (`cell`) AUC / P@100 | **`gbm`** AUC / P@100 |
|---|---|---|---|
| Raises a **bigger round** within 18 months: at least $5M and at least 1.5x its largest round so far | 4.8% | 0.658 / 10.7% | **0.765 / 17.8%** |
| Starts any new round within 18 months | ~20% | 0.692 / 49.7% | **0.732 / 61.8%** |
| Goes public within 36 months | 0.8% | 0.812 / 13.1% | **0.894 / 27.1%** |

`gbm` (LightGBM) beats the baselines in every test year. `investup score` and
`investup digest` use it by default and list the features that pushed each score up
most (from SHAP contributions).

[`docs/digests/2026-06-30.md`](docs/digests/2026-06-30.md) is a sample digest. It covers
the 2,200 companies that filed in Q2 2026, ranked by bigger-round odds, with an IPO
watch and the biggest raises (e.g. Baseten, Saronic, Ramp, Shield AI).

**Known limitations:**
- Acquisitions aren't tracked yet, so a company that was bought can still show up.
- "Went public" includes tiny self-filed S-1 listings, not only venture-backed IPOs.
- Precision varies with the market. The bigger-round model's P@100 ranged from 35%
  (2021) to 6% (2023).

## Development

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

## History

The original 2015 Node/Express + React app is in git history at commit `ebc039f`. It was
removed because it depended on a retired Crunchbase API, its model leaked its label (see
the audit), and its Crunchbase-derived data can't be redistributed.

## License

Code: MIT (see [LICENSE](LICENSE)). SEC filing data is US public-domain government data.
