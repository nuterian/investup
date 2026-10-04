# Investup site

A static site over the files written by `investup export`. No backend.

```bash
# from the repo root: build the data
uv run investup export            # -> site/public/data/

# then the site
cd site
npm install
npm run dev                       # http://localhost:5173
npm test
npm run build                     # -> site/dist/
```

Pages: dashboard (`#/`), company (`#/c/<cik>`), explore (`#/explore?...`) and
method (`#/method`). See `docs/FRONTEND_PLAN.md` for the design.
