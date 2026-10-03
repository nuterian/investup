# Investup

An open, explainable early-signal engine for private companies, built entirely from
public records.

Investup tracks every US company that reports a private raise to the SEC (Form D).
It shows how fast each company is moving compared with its peers, and (soon) estimates
the chance it raises again in the next 18 months, with the reasons behind every number.

> **Status: rebuilding.** This started as a 2015 class project built on Crunchbase data.
> [`docs/AUDIT_AND_ROADMAP.md`](docs/AUDIT_AND_ROADMAP.md) explains why it's being rebuilt
> and what the plan is. Right now we're in Phase 1: the open funding ledger.

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
uv sync

# The SEC requires a contact in the User-Agent for automated downloads.
export INVESTUP_USER_AGENT="Your Name you@example.com"

uv run investup download --start 2015q1   # quarterly Form D ZIPs -> data/raw/formd/
uv run investup load                      # -> data/investup.duckdb
uv run investup stats                     # yearly coverage summary
```

If the SEC moves the files again, set `INVESTUP_FORMD_URL_TEMPLATE`, for example
`https://www.sec.gov/.../{year}q{quarter}_d.zip`. You can also download the ZIPs by hand into
`data/raw/formd/`.

### Querying the ledger

```bash
uv run python -c "import duckdb; c = duckdb.connect('data/investup.duckdb'); \
  print(c.sql(\"SELECT * FROM company_snapshot(DATE '2020-01-01') ORDER BY raised_last_24m DESC LIMIT 20\"))"
```

| Object | What it is |
|---|---|
| `stg_formd_*` | Raw SEC rows, all text, tagged with `source_quarter` |
| `formd_filing` | One typed row per filing: primary issuer joined to the offering |
| `raise_event` | Operating-company raises (investment funds excluded), with `new_money` derived from amendment chains |
| `company_snapshot(as_of)` | What was publicly known about each company on `as_of` |
| `raised_again_label(as_of, months)` | Phase 2 training label: did the company report new money in the next N months? |

## Development

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

## Legacy 2015 app

The original Node/Express + React 0.13 app (`index.js`, `modules/`, `public/`, `views/`)
is still in the tree for reference but **doesn't work**. It depends on a retired Crunchbase
API, and its model leaks its label (see the audit). It will be removed. Its
Crunchbase-derived data under `data/` can't be redistributed and will be removed too.

## License

Code: MIT (see [LICENSE](LICENSE)). SEC filing data is US public-domain government data.
