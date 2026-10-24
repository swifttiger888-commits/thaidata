# AGENTS.md — ThaiData UK

Repo for thaidata.uk, a static Thai-restaurant directory on Cloudflare Pages (auto-deploys on push to `main`).

## Hard rules

- **The whole repo root is published as-is.** Never commit anything internal unless it can be public. Internal paths (docs/, analysis/, tests/, scripts/, schemas/, .hermes/, wrangler.toml, requirements.txt) are 404'd on the site via `_redirects` — add new internal directories there. Secrets go in `secrets/` (gitignored, never committed).
- **Never run `git clean -x`.** It wiped `secrets/` once.
- **`data/restaurants.json` is the single source of truth** for counts, ratings, cities and venue lists. Never hand-edit generated pages (`r/`, `cities/`) — regenerate with the scripts in `scripts/`. Counts appear on hand-maintained pages too (index, faq, about, guides, learn, restaurants, llms.txt); update them together when data changes.
- **Run `pytest tests/` and `python scripts/ci_check.py` before pushing.** The tests guard against stale counts and JSON drift; CI runs them on every push.
- Pages project name is `thaidata`; builds use the dashboard settings, not `wrangler.toml`. Deploy preview URLs (`*.pages.dev`) are permanent snapshots and are noindexed.

## Where things live

- `data/` — datasets (restaurants, exclusions, festivals, menus, enrichment)
- `scripts/` — data fetch + page generators; `functions/` — Pages Functions (admin, search, middleware)
- `tests/` — pytest suite incl. the stale-count guard
- `docs/thaidata-environment-overview.md` — full environment, tokens, API and deployment notes
- `docs/mobile-layout-contrast-guidelines.md`, `docs/cta-link-accessibility-guidelines.md` — design standards

Recompute any figure from `data/restaurants.json` rather than trusting a number found in prose, comments or this file.
