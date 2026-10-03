# Investup — Audit, Research & Roadmap (Oct 2026)

## TL;DR

Investup is a 2015 class project (Node/Express + React 0.13 + D3) for searching ~28.5k
Crunchbase companies and showing each one a "success score" from per-category decision trees.
It doesn't work as a product today, and what it predicted was never very meaningful:

1. **It's dead.** Profile pages call the Crunchbase **v3** `user_key` API with a 2015 key.
   Crunchbase now offers only v4 under paid Enterprise or Applications licenses. Any failed
   call also crashes the whole server.
2. **The model leaks its label.** All 58 trees split first on `num_acquisitions ≥ 1 → success`,
   and age is the most-used feature after that. The model mostly learned "older companies that
   have already exited or acquired others are successful", which can't tell you anything about
   companies that haven't exited yet.
3. **A Crunchbase API key is committed to a public repo** (`modules/utils.js`), and has been
   since 2015.

The idea itself (find early signals of which startups will grow) is more useful now than in
2015, and there are now free, legally clean data sources for it. The plan below rebuilds the
project as an **open, explainable startup-signal engine**. It is built on public filings and
alternative data rather than a licensed Crunchbase dump.

---

## 1. What the repo does today

| Layer | What's there |
|---|---|
| Server | `index.js` (Express 4, ~500 lines): search, related companies, competitors, profile, stats |
| Data | `data/companies_index.json`: 28,504 companies, each with name, logo URL, precomputed score `s`, age in months `a` and categories `c`. `categories_freq.json` holds per-category funding-rate stats. `data/trees/*.json` holds 58 serialized decision trees, one per category |
| Profiles | Built on demand from `api.crunchbase.com/v/3/organizations/<permalink>`, then cached to `data/profiles/*.json` |
| Model | `machine_learning@0.0.8` DecisionTree. Input: 11 hand-made features plus the precomputed score `s`. Output is turned into a score with `0.5 + s·0.5·P(1)` |
| "Trends" | Hand-written rules in `tickerRaters`: "All-Star" means exited and score ≥ 0.85. "Hot" is based on funding velocity against the category average |
| Frontend | React 0.13 JSX, jQuery, Director router, D3 v3 funding chart. The compiled bundle is committed |
| Tests / CI | None |

**Missing from the repo:** the training pipeline, the raw data (`/data/companies` is
gitignored), the code that produced `s`, and the label definition. None of the model can be
reproduced.

## 2. Audit findings

### 2.1 Modeling & data science (the important part)

| # | Finding | Evidence | Impact |
|---|---|---|---|
| M1 | **Label leakage.** Every tree's root is `num_acquisitions ≥ 1`, and that branch is 100% class 1 (for example, 553 of 553 in Software). Success apparently included "has made acquisitions", and that same count is also a feature. | `data/trees/*.json`, root node `col: 6` in all 58 | The model's biggest "insight" just restates the label |
| M2 | **Look-ahead and survivorship bias.** Features are built from the company's *current* state, which includes events after the outcome (age is measured up to the acquisition date, and rounds/investors are counted over the company's whole life). Nothing is computed "as of" an earlier date. | `profileFeatures.age`, `funding_rounds`, etc. | Scores can't be used to predict anything. The model mostly rewards older, already-successful companies (the top 5 are Google, PayPal, Facebook, Groupon and Alibaba) |
| M3 | **Circular score.** The prior score `s` is a tree feature (`col 11`, the 2nd most-used split), and the output is then multiplied by `s` again. | `utils.getPredictionInput`, `calcSuccessScores` | The final score mostly reflects `s`, whose origin is undocumented |
| M4 | **Features differ between training and serving.** The trees split `funding_rounds` on numbers ("7"), but at serving time `profileFeatures.funding_rounds` returns an array of `{d, a}`. `num_employees` returns strings like `"11-50"`. `age` is measured against *today*, so it drifts every month. | `modules/profileFeatures.js` | Live predictions are wrong even where the API still works |
| M5 | **No evaluation.** No train/test split, no metrics, no calibration, no baseline. A single unpruned decision tree per category, some trained on a few hundred rows. | none in repo | Nobody can tell whether the model beats a coin flip or plain "total funding" |
| M6 | **The score isn't a probability**, but the UI shows it as a "chance of success". | `public/js/src/main.js` profile visuals | Misleading |

### 2.2 Correctness & reliability

- **Server crash on any API failure.** `/profile` dereferences `profile.total_funding`
  without checking whether `saveProfile` returned `null` (`index.js:483`). I reproduced this:
  a failed Crunchbase request kills the process.
- **Dead upstream.** The API has moved to v4, which needs a paid Enterprise or Applications
  license. The v3 endpoint with a 2015 key won't serve data, so every uncached profile
  request fails. (I couldn't reach api.crunchbase.com from this sandbox, so this is inferred
  rather than tested.)
- `/stats` overwrites the shared in-memory index (`meta.s = profile.success.all`,
  `index.js:56`), so each call changes later search rankings.
- The LRU cache never updates recency: it calls `queue.slice` where it needs `queue.splice`
  (`index.js:385`). It also holds 11 entries, not 10.
- `/related` mutates the request body array while iterating over it.
- Implicit globals: `profileData` (`index.js:434`) and `_a` (`modules/utils.js:33`). This is
  a race between concurrent requests.
- Search scans all 28.5k entries for every keystroke (O(N)), and `/stats` reads every cached
  profile from disk on each call.
- `ranker` writes `data/ranks.json` with fire-and-forget `writeFile` and silently ignores
  errors.

### 2.3 Security

- **Hardcoded API key** in `modules/utils.js` (public repo, in git history since 2015). Revoke
  it in the Crunchbase account even if v3 is dead. Then move secrets to environment variables.
  Scrubbing git history is optional once the key is revoked.
- `/meta`, `/profile` and `/competitors` pass `req.query.p` straight into a file path
  (`PROFILE_DIR + permalink + ".json"`). That's a **path traversal** risk for both reads and
  writes.
- Mixed content: Google Fonts is loaded over `http://`.
- Dependencies from 2015 (Express 4.12, Jade 1.x, now renamed Pug and with known template
  RCE CVEs, React 0.13, D3 v3) have many known vulnerabilities. `machine_learning@0.0.8` is
  unmaintained.
- No rate limiting, input validation or CORS policy.

### 2.4 Licensing & data rights

- `companies_index.json` and the trees come from Crunchbase data. Crunchbase's terms don't
  allow redistributing their data, so publishing that file in a public repo is a licensing
  liability. Remove it in the rebuild.
- `package.json` still names the old repo (`web-search-project`) and the project has no
  LICENSE file.

### 2.5 What's worth keeping

- The **product idea**: search a company, see a score you can explain, compare it with
  competitors and its category, and browse "hot" and "all-star" lists.
- The **velocity idea** in `getRateFromProfile`: funding per month compared with the category
  mean and standard deviation. Relative momentum within a category is still a good signal.
- The UX ideas: related companies, competitor rank ("#3 of 9"), funding timeline chart.

Everything else (code, model, data) should be replaced rather than upgraded.

---
## 3. Research: data, science and market (2026)

### 3.1 Is the Crunchbase data still available?

- **Live Crunchbase (API v4 or daily CSV)** needs an Enterprise or Applications license.
  Pricing is quote-only, and the license forbids redistributing the data. The free Basic tier
  has no funding data, and it may no longer be offered (I found conflicting reports).
  Crunchbase is fine for a private tool if you pay for it, but it can't power an open project.
- **The old snapshots still exist:**
  - Kaggle: 2013 snapshot (`justinas/startup-investments`, `mauriciocap/crunchbase2013`).
  - GitHub: the 2015 export (`notpeter/crunchbase-data`, CC-BY-NC).

  They're about a decade stale. They're useful as a **historical backtest set**, since we now
  know how those companies turned out, but not as a product data source.

### 3.2 Free, legally clean alternatives

| Need | Source | Notes |
|---|---|---|
| US funding events | **SEC Form D** quarterly data sets (2008–2026) | Free. Covers Reg D raises: amount offered and sold, investor count, executives, industry, first-sale date. No valuations and no investor names. Not every startup files. |
| US small raises | **SEC Form C** (Reg CF) data sets | Crowdfunding issuers, including their financials |
| US exits | EDGAR S-1/424B (IPOs), 8-K (acquisitions by public companies), submissions JSON API | Free |
| UK funding and failures | **Companies House API**: SH01 share allotments (UK funding rounds), dissolutions, accounts, officers | Free under the Open Government Licence. Dissolutions give real failure labels, which Crunchbase lacks. |
| Entity resolution | GLEIF (CC0), Wikidata (CC0), company domains | Joins sources together. Wikidata also has notable acquisitions. |
| Hiring velocity | Public ATS job-board APIs: Greenhouse, Lever, Ashby | No auth. Needs each company's board token. |
| Dev traction | GH Archive | Stars, contributors and commit activity over time |
| Attention | HN Algolia API, Product Hunt API (non-commercial), GDELT news | Free |
| Web prominence | Tranco top-1M (CC-BY), Common Crawl host graph | Rough proxy, mostly useful for larger companies |
| Labeled cohorts | `yc-oss/api` (YC directory JSON) | Licensing is grey. Attribute it and don't bulk-republish. |
| **Avoid** | LinkedIn and Wellfound scraping (ToS; *hiQ v. LinkedIn* ended in an injunction), paid vendors' data in an open repo | |

Commercial platforms (PitchBook, CB Insights, Dealroom, Harmonic, Specter, Tracxn) cost
roughly $6k to over $100k a year according to third-party estimates. None of them allow
redistribution.

### 3.3 What the research says about predicting startup success

- **Labels.** The field is moving from "eventual exit" toward **short-horizon milestones** like
  "raises the next round within 12–24 months" (Loukas et al. 2022, arXiv:2210.14195, a review
  of 29 studies). These milestones are observed sooner, there are more of them, and they're
  less biased by survivorship.
- **Features that matter** (meta-analysis, arXiv:2507.09675):
  - firm basics (age, location, sector);
  - investor quality and structure;
  - funding history and momentum;
  - digital traction.

  Founder background matters a lot, but it mostly comes from LinkedIn-type data.
- **Realistic performance.**
  - A bias-free design with gradient boosting reaches about 57% precision and 34% recall
    (Żbikowski & Antosiuk 2021).
  - VCBench (arXiv:2509.14448) puts the base rate of "big outcomes" at about 1.9%, with top
    models reaching about 29% precision.

  So doing 3–10× better than the base rate is a good result. Anyone claiming "90% accuracy"
  is leaking labels, which is exactly what Investup 2015 did.
- **Pitfalls that the field agrees on:**
  - Build every feature *as of* the prediction date, which means a point-in-time feature store.
  - Split train and test by time, never randomly.
  - Report Precision@N and calibration rather than accuracy.
  - Watch for survivorship bias, since failed companies are under-recorded.

### 3.4 Where the opportunity is

Commercial "signal" tools (Harmonic, Specter, SignalFire Beacon, EQT Motherbrain) have shown
that the valuable product is **early alerts from traction time series**, not a static score.
They are closed, expensive and focused on US software.

An individual or open project can stand out in four ways:

1. **Built only from open records.** Every score traces back to public filings, so it's
   reproducible and auditable.
2. **Underserved coverage.** Companies that file Form D, Form C or UK SH01 but that vendors
   miss: non-software, regional and crowdfunded companies.
3. **Honest, published backtests.** "If you'd followed our top-50 list in 2019, here's what
   happened."
4. **An open dataset as a by-product.** A clean, CC0/OGL "private funding ledger"
   (Form D first, Companies House later) is useful in its own right and builds credibility and traffic.

---

## 4. Product vision

> **Investup: an open early-signal engine for private companies.**
> It tracks every company that files a private raise with the SEC, shows how fast each one
> is moving compared with its peers, and estimates the chance it raises again or fails in the
> next 18 months. Every number comes with the reasons behind it.

**Primary users:**

- Angels, scouts, and small or emerging VC funds that can't afford a $25k seat.
- Secondary users: founders benchmarking against peers, journalists and researchers.

**Core jobs:**

1. **Discover:** "Show me Series-A-stage climate-hardware companies in Texas whose momentum
   jumped this quarter."
2. **Evaluate:** a company page with a funding timeline, peer percentile, calibrated
   probabilities and the top drivers behind them.
3. **Monitor:** watchlists and a weekly digest of new filings and momentum changes.

## 5. Roadmap

### Phase 0: Triage

- [ ] **Revoke the Crunchbase key** in the Crunchbase account, then remove it from code. Load
  secrets from environment variables.
- [ ] Tag the current state as `v0-2015-classproject` (commit `ebc039f`), then delete the old
  app.
- [ ] Remove Crunchbase-derived data (`data/companies_index.json`, `data/trees/`) from the
  default branch. That data can't be redistributed.
- [ ] Add a LICENSE (e.g. MIT for code, CC0/OGL notes for data) and fix `package.json`
  metadata, or replace it.

### Phase 1: Open data foundation

**Goal:** a reproducible, point-in-time **funding ledger**.

- **Stack:**
  - Python 3.12 and **DuckDB/Parquet** for storage, which is a single file and needs no
    server.
  - `uv` for environments.
  - Scheduled pipelines through GitHub Actions or cron.
- **Ingestors:**
  1. SEC Form D quarterly sets (2008–present), parsed into issuers, offerings, amendments and
     related persons. *(started)*
  2. SEC Form C.
  3. EDGAR S-1/424B and 8-K exits.
  4. Wikidata for exits and parent companies.
  5. *(Deferred to Phase 5: UK Companies House.)*
- **Entity resolution:** CIK or company number as the primary key, plus normalized name, state
  and executive overlap, and the domain once we have it. Store match confidence.
- **Bitemporal tables:** every fact gets both `event_date` and `known_at` (filing date). This
  one design decision is what prevents the look-ahead bias that broke the 2015 model.
- **Deliverables:**
  - `investup.duckdb`, plus a published, versioned open dataset.
  - Data-quality report: coverage by year and sector, match rates.

### Phase 2: An honest model

**Goal:** calibrated, explainable probabilities that a backtest shows are better than
baselines.

- **Labels**, all observable from filings, at a fixed 18-month horizon from snapshot date *t*:
  - **Raise again:** a new Form D or amendment with a higher amount sold.
  - **Fail:** no filings for a long period, or a state-level dissolution where available.
    US failure labels are weaker than the UK's, which is a known limitation.
  - **Exit:** IPO filing or 8-K acquisition, when available.
- **Features as of *t* only:**
  - age;
  - sector and geography;
  - raise count;
  - cumulative and last raise size;
  - months since last raise;
  - **raise velocity z-score within sector and vintage** (the 2015 `getRateFromProfile` idea,
    done properly);
  - investor count;
  - number of executives and directors, and their past companies' outcomes (a founder track
    record built from Form D related persons);
  - sector-level heat.
- **Models:**
  - Baselines first: base rate, and "last raise size" alone.
  - Then LightGBM with isotonic calibration.
  - SHAP for per-company explanations.
- **Evaluation:**
  - Rolling time splits (train ≤ 2018 → test 2019–20, and so on).
  - Metrics: Precision@50/100, PR-AUC, Brier score, calibration plots, broken down by sector
    and country.
  - Publish a model card and a backtest report.
- **Optional:** re-run the same pipeline on the 2013 Crunchbase snapshot as a sanity check
  against known outcomes. Do this locally only and don't redistribute it.

### Phase 3: Traction signals

**Goal:** time-series signals that are known to lead funding.

- Resolve domains for active companies using Form D, Wikidata and search.
- Take weekly snapshots of:
  - open roles from Greenhouse, Lever and Ashby (hiring velocity);
  - GitHub org activity (GH Archive);
  - HN and GDELT mentions;
  - Tranco rank.
- These signals only exist from the day we start collecting them, so **start collecting
  early**, even before Phase 2 is finished. Every week of delay is a week of history lost.
- Add these signals as features after about 12 months of history, and as momentum alerts
  right away.

### Phase 4: Product

- **Backend:** FastAPI over DuckDB, with search (DuckDB FTS, or Meilisearch if needed),
  company, peers, screener and watchlist endpoints.
- **Frontend:** a modern TypeScript SPA (React + Vite, or Next.js) that keeps the good 2015
  ideas: search, company page, funding timeline chart, peer rank ("#3 of 41 in NY fintech,
  2021 vintage"), and Hot and All-Star lists, now defined by calibrated momentum.
- **Watchlists and a weekly email digest.** This is the feature that brings people back.
- **LLM assist, where it helps and can be checked:**
  - Classify issuers into a modern sector taxonomy from their website text. Form D's industry
    codes are coarse.
  - Write a short, cited summary of each company's filing history.
  - The LLM never produces the score itself.
- **Public read-only API and dataset downloads.**

### Phase 5: Optional extensions

- Add more countries with open registries: UK Companies House first (SH01 rounds and
  dissolutions), then e.g. France's INPI and BODACC, Norway's Brønnøysund registers,
  Singapore's ACRA.
- A founder-network graph (people who appear across many filings).
- *(Ruled out by the open-source decision: licensed vendor enrichment.)*

## 6. How we'll know it's valuable

| Area | Target |
|---|---|
| Model | Precision@100 for "raises again within 18 months" at **≥3× the base rate** on held-out years. Brier score better than the baseline. Calibration error under 5 points. |
| Data | Over 90% of Form D issuers since 2015 resolved to a stable entity. Coverage report by year and industry. |
| Product | Weekly digest open rate. At least 10 real users (angels or scouts) who keep a watchlist. At least one "found it here first" story. |

## 7. Risks

| Risk | Mitigation |
|---|---|
| Form D misses companies that raise without filing, and SAFE reporting is uneven | Combine with Form C and traction signals. State coverage limits in the UI. |
| Entity-resolution errors | Store match confidence. Let users flag and fix wrong matches. |
| Labels are proxies (raising again ≠ success) | Show several outcomes (raise / fail / exit) instead of one "success" number |
| Scraping and ToS exposure | Use only official APIs and bulk files. No LinkedIn or Wellfound. |
| Scope creep for a solo builder | Phases 0–2 are useful on their own as an open dataset plus a backtest report. Ship them before building any UI. |

## 8. Decisions (Oct 2026)

| Question | Decision | What it means |
|---|---|---|
| Audience and business model | **Open source** | Open, redistributable data only. Crunchbase and paid vendors are out. |
| Geography | **US only** to start | Form D, Form C and EDGAR. Companies House moves to Phase 5. |
| Stack | **Python** for data and ML, **TypeScript** frontend | DuckDB, LightGBM and FastAPI on the backend; React + Vite or Next.js on the frontend. |

## 9. Progress

- [x] Audit, research and roadmap (this document)
- [x] Crunchbase key moved out of the code into `CRUNCHBASE_API_KEY`. **Revoke the old key
      in the Crunchbase account**: it's still in git history.
- [x] MIT LICENSE, Python project (`uv`), CI (ruff + pytest)
- [x] Form D loader: downloader, schema-checked TSV loader, DuckDB staging tables
- [x] Ledger views: `formd_filing`, `raise_event` (new money from amendment chains, funds
      excluded), `company_snapshot(as_of)`, `raised_again_label(as_of, months)`
- [x] First real load: all 74 quarterly files (2008Q1–2026Q2), about 190 MB, with no
      schema warnings. Fixes this required:
      - the downloader now reads the SEC index page, because file paths and suffixes vary;
      - added the `YEAROFINC_VALUE_ENTERED` header;
      - parse both filing-date formats (timestamps before 2020Q3, `30-SEP-2020` after).
- [x] Data-quality rules from the real data:
      - same-day correction filings replace the typo (e.g. a $105B typo corrected to $105M);
      - implausible amounts are flagged (32 events);
      - coarse sectors and an `is_venture_sector` filter.
- [x] Legacy 2015 app and Crunchbase-derived `data/` removed (history: `ebc039f`)
- [x] EDGAR milestones from the quarterly master indexes (2008Q1–2026Q3): point-in-time
      public status, IPO registration and prospectus, fund filings, Form C, Reg A.
      Checked against Airbnb, Snowflake, Coinbase and Uber.
- [x] Universe hygiene:
      - US headquarters only. This removes Canadian junior miners that file Form D for
        US placements.
      - Name rules for separate accounts, funds, SPVs, co-invest/feeder vehicles and LLPs.
      - Deterministic tie-breaks in snapshots, which fixed universe size varying between
        runs.
- [x] Phase 2 baseline:
      - `features(as_of)` covers raise history, recency, offering status, revenue range,
        sector heat and team track record (people on earlier companies and earlier IPOs).
      - `investup backtest` runs a walk-forward backtest with AUC, AP, P@k and Brier
        (metrics are unit-tested).
      - `investup score` ranks today's private companies, with the reason for each score.
- [x] LightGBM challenger (`gbm`) with per-company explanations from SHAP contributions.
      It beats every baseline in every test year; see the results below.
- [x] Size-aware `step_up` label: a new round of at least $5M and at least 1.5x the largest
      round so far, within 18 months. Base rate about 5%; now the default label.
- [x] `investup digest`: recent filers ranked by bigger-round and IPO odds, with reasons
      (sample in `docs/digests/`)
- [x] Calibration tables in the backtest reports. They showed the top 1% is
      over-confident. A held-out Platt correction made it worse (regime shift), so it was
      removed. The site shows historical hit rates by rank band instead, made monotone
      in the export.
- [x] `investup export` for the static site: summary, scored universe, lists (including
      quarter-over-quarter movers, repeat founders and new S-1 filers), search index and
      1,024 company-detail shards
- [ ] Acquisition tracking. The only reachable host is www.sec.gov; acquirer 8-K text
      search lives on efts.sec.gov, and Wikidata isn't reachable from the environment.
- [x] Static site source (`site/`): dashboard, company page, screener with CSV export,
      methodology page, plus the GitHub Pages workflow. No API server; see
      `docs/FRONTEND_PLAN.md`.
- [x] Site installed, type-checked, tested and built, and checked in a headless browser
      against real data
- [x] Daily freshness: live ingest of every Form D filed since the last quarterly data set
      (EDGAR submission text, parsed into the same staging tables), current-quarter EDGAR
      index refresh, `investup check` before deploy, daily `Site` workflow with keep-alive,
      quarterly `Backtests` workflow that opens a PR
- [ ] Merge to the default branch and do the one-time GitHub setup (see README)
- [ ] Form C as its own funding source, entity resolution across renamed CIKs,
      data-quality report

### Backtest results (walk-forward, test years 2016–2024)

| Label | Base rate | Model | AUC | P@100 | P@1000 |
|---|---|---|---|---|---|
| Bigger round within 18 months | 4.8% | `cell` model | 0.658 | 10.7% | 11.0% |
| Bigger round within 18 months | 4.8% | **`gbm`** | **0.765** | **17.8%** | **16.8%** |
| New round within 18 months | ~20% | `recency` rule | 0.675 | 58.8% | 46.5% |
| New round within 18 months | ~20% | `cell` model | 0.692 | 49.7% | 46.9% |
| New round within 18 months | ~20% | **`gbm`** | **0.732** | **61.8%** | **49.7%** |
| Went public within 36 months | ~0.8% | `cell` model | 0.812 | 13.1% | 6.3% |
| Went public within 36 months | ~0.8% | **`gbm`** | **0.894** | **27.1%** | **8.8%** |

The IPO model's main drivers are state, total raised, sector, team size, last raise size
and the team's prior IPO companies. Its live watchlist (2026-06-30) is mostly well-funded
therapeutics and medtech companies plus a few tech companies. The `next_round` live list
is dominated by serial small filers, which is why the size-aware label is the next
priority.

For the 2019 test year, 193 of the 208 companies that went public did so through a priced
IPO, so this label isn't dominated by shell listings. Twenty of the cell model's top 100
on 2019-01-01 went public within 36 months, including Fulcrum, Harpoon, Gossamer Bio,
ShockWave Medical and Berkeley Lights.

### First numbers from the real ledger

| | |
|---|---|
| Operating-company Form D filings | about 15–23k a year since 2010 |
| Venture-sector companies raising per year | about 9–12k |
| Venture-sector new money | about $45–200B a year; 2021 peak about $203B |
| Base rate for Phase 2 | About 24% of active venture-sector companies reported any new money within 18 months, and about 20% started a new round. This was before the universe was narrowed to US, non-vehicle companies; see the backtest results above. |
| Known coverage gaps | Some large companies (e.g. OpenAI, Anthropic, Rippling) don't show up under their own name. Stripe, Databricks, Figma and xAI do. |
