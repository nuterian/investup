# Investup — Audit, Research & Roadmap (Oct 2026)

## TL;DR

Investup is a 2015 class project (Node/Express + React 0.13 + D3) for searching ~28.5k
Crunchbase companies and showing each one a "success score" from per-category decision trees.
It doesn't work as a product today, and what it predicted was never very meaningful:

1. **It's dead.** Profile pages call the Crunchbase **v3** API, which has been retired. Any
   failed call also crashes the whole server.
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
- **Dead upstream.** The Crunchbase v3 `user_key` API has been retired, so every uncached
  profile request fails.
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
