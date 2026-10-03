# Frontend plan: a minimal, high-signal Investup site

## Goal

One small site that answers three questions fast:

1. **What's happening?** The private funding market this quarter, and who's likely to
   break out next.
2. **Tell me about this company.** Its funding history, its odds of a bigger round or an
   IPO, and why.
3. **Find me companies like X.** Filter the scored universe by sector, state, size and
   odds.

Every number on screen needs context: compared with what, how often it's been right, and
why. If a number can't carry that context, it doesn't go on the page.

## Simplest architecture: a static site, no server

```
investup pipeline (Python)                       browser
──────────────────────────                       ───────
download → load → score → export ──►  site/data/*.json  ──►  Vite + React + TS app
                                       (static files)          (GitHub Pages)
```

- **No backend.** `investup export` writes a few JSON files. The app is static files that
  read them. Hosting is free (GitHub Pages), and nothing has to run between data updates.
- **Refresh:** a scheduled GitHub Action runs `download → load → score → export → deploy`
  once a quarter, after the SEC publishes new Form D data. It needs one repository
  secret, the SEC contact User-Agent.
- **Why not an API server:** the data changes quarterly and the scored universe is small
  (~22k companies), so a server adds cost and moving parts without adding value.
- **Why not DuckDB-WASM in the browser:** it's powerful, but it means a 5–10 MB download
  for a site whose questions are known in advance. We can add it later if people want
  ad-hoc queries.

### Data files (`investup export`)

| File | Contents | Approx. size (gzip) |
|---|---|---|
| `summary.json` | Quarter KPIs, quarterly funding series, sector momentum, model track record, data date | < 50 KB |
| `universe.json` | Current scored universe (~22k rows): CIK, name, state, sector, last raise date, total raised, largest round, P(bigger round), P(IPO), percentiles | ~600 KB |
| `lists.json` | The curated lists below (top 25 each) | < 50 KB |
| `search.json` | Name + CIK + state + last filing year for every operating company that raised since 2015 (~120k), so lookup covers more than the scored universe | ~1.5 MB, loaded on first search |
| `c/<shard>.json` | Company detail, split into 256 shards by CIK: raise timeline, people named on filings and their other companies, top reasons for each score, peers | ~5–15 KB per company |

All scores come from `gbm`, using the same `score_current()` path as `investup digest`.

## Pages (three, plus a methodology page)

Wireframe numbers and names are illustrative. Some come from the 2026-06-30 digest; others, such as the year-over-year change and the people, are placeholders.

### 1. Home: "This quarter"

```
┌───────────────────────────────────────────────────────────────────┐
│ investup              [ Search companies…            ⌘K ]          │
├───────────────────────────────────────────────────────────────────┤
│ Q2 2026 · data through 2026-06-30                                  │
│                                                                    │
│  2,200 companies raised    $66.7B venture money    +12% vs Q2 '25  │
│                                                                    │
│ Funding pulse  ▁▂▃▅█▆▅▄▅▆▅  (venture $ by quarter, 2015–now)        │
│                                                                    │
│ Likely to raise a bigger round        IPO watch                    │
│ 1 Attotude · Tech · CA     28% (6x)   1 Route 92 Medical  77%      │
│ 2 SmartAC.com · Tech · TX  26%        2 Magnus Medical    60%      │
│ …                                     …                            │
│                                                                    │
│ Movers: biggest jump in odds since    Repeat founders: new companies│
│ last quarter                          whose team built an earlier   │
│ …                                     IPO company                   │
│                                                                    │
│ Sector momentum (raises, last 12m vs prior 12m)                    │
│ Health Care ███████ +18%   Technology █████ +9%   Energy ██ −4%     │
│                                                                    │
│ Model track record: top-100 bigger-round picks were 3.5x the base  │
│ rate in backtests (2016–2024). How we score →                      │
└───────────────────────────────────────────────────────────────────┘
```

**The lists, ordered by signal:**
1. **Likely to raise a bigger round:** top `step_up` probabilities among companies active
   in the last 12 months. Each shows its multiple of the 4.8% base rate.
2. **IPO watch:** top `went_public` probabilities, excluding tiny self-filed S-1 shells
   (total raised under $5M).
3. **Movers:** the largest increase in bigger-round odds since the previous quarter's
   scores. This needs the export to also score the previous data date, which is cheap
   because the backtest already builds that snapshot.
4. **Repeat founders:** companies whose first filing was in the last 12 months and whose
   team includes people from a prior IPO company.
5. **Biggest raises this quarter.**
6. **Fresh IPO pipeline:** universe companies that filed an S-1/F-1 this quarter.

### 2. Company page

```
┌───────────────────────────────────────────────────────────────────┐
│ Route 92 Medical, Inc.            Health Care · CA · CIK 1675633 ↗ │
│                                                                    │
│ Bigger round in 18m   5.5%  (1.1x base)                            │
│ IPO in 36m           77.4%  (top 0.1%)                             │
│   why: team's prior IPO companies: 7 · total raised: $208M ·       │
│        top 2% for 24-month raise size in sector                    │
│                                                                    │
│ Funding timeline                                                   │
│  $   ▇      ▇▇        ▇▇▇▇        (bars = new money per filing)    │
│     2017   2019      2022        2026                              │
│                                                                    │
│ Total raised $208M · Largest round $90M · 7 rounds · First filing  │
│ 2016 · Investors in last raise 41                                  │
│                                                                    │
│ People on filings   Jane Doe (Exec) — also: Acme Bio (IPO 2019)    │
│ Peers               3 similar Health Care companies in CA, by odds │
│ Filings             every Form D, with links to SEC EDGAR          │
└───────────────────────────────────────────────────────────────────┘
```

- **Scores** always show the base-rate multiple or percentile and the top three reasons,
  in plain words.
- **People:** names and roles exactly as they appear in public filings, plus their other
  companies. No addresses.
- **Companies outside the scored universe** (public, funds, inactive) get the timeline
  and facts, plus a clear "not scored because…" line.

### 3. Explore (screener)

- One sortable table over `universe.json`.
- **Filters:** sector, state, total raised range, last raise within N months, minimum
  P(bigger round), minimum P(IPO), and "repeat founders only".
- **Display:** the first 100 rows, with "show more"; sorting and filtering happen in
  memory (22k rows is instant).
- **CSV download** of the filtered rows.

### 4. How we score (methodology)

- **Results:** a plain-language summary of each label and its backtest results (from
  `docs/backtests/`), including the calibration table.
- **Data sources:** where the data comes from and what Form D misses.
- **Limitations:** acquisitions aren't tracked, and these scores aren't advice.

## Design rules

- **One accent colour**, neutral greys, light and dark mode, and a system font stack.
- **Numbers carry their reference:** probability plus multiple of the base rate,
  percentile in sector, change since last quarter.
- **No decorative charts.** Four visuals in total: funding pulse (sparkline), sector
  momentum (bars), company funding timeline (bars), and calibration (table).
- **Loading:** fast on first paint. The home page needs only `summary.json` and
  `lists.json`; the rest loads on demand.
- **Shareable URLs:** every company and every screener state has its own link
  (`/c/1675633`, `/explore?sector=Health+Care&min_ipo=0.2`).
- **Optional personal watchlist:** a star button saved in the browser's localStorage. No
  accounts.

## Tech choices (minimal)

| Need | Choice | Why |
|---|---|---|
| Build | Vite + TypeScript | The stack you already approved; one config file |
| UI | React | Small component count; familiar |
| Routing | Hash routes (`#/c/123`) | Works on GitHub Pages with no server rewrites |
| Charts | Hand-rolled SVG (about 3 small components) | Sparkline and bars don't justify a chart library |
| Search | Prefix and token match over `search.json` in a web worker | 120k names; no library needed |
| Styling | Plain CSS with CSS variables | No framework to learn or upgrade |
| Tests | Vitest for data formatting and search; Python tests for the export schema | |

**Runtime dependencies:** `react` and `react-dom` only.

## Milestones

1. **Export (Python):** `investup export` writes the files above, a JSON schema test, and
   previous-quarter scores for "Movers".
2. **App skeleton:** layout, search box, company page from shard files.
3. **Home dashboard:** KPIs, funding pulse, the curated lists, sector momentum.
4. **Explore:** screener table, filters, CSV download, shareable URLs.
5. **Methodology page and deploy:** GitHub Pages workflow, plus a quarterly refresh
   Action with the SEC User-Agent secret.

Each milestone is usable on its own. After milestone 2 you can already look up any
company.

## Prerequisites and open decisions

- **Network:** building the frontend needs `registry.npmjs.org` added to the cloud
  environment's allowed domains (the same place `pypi.org` was added).
- **Hosting:** a public GitHub Pages site (recommended; the repo and data are already
  public), or local only (`npm run dev` against exported files).
- **People names:** show executives and directors from Form D (recommended: public
  record, and it powers the track-record signal), or show counts only.
