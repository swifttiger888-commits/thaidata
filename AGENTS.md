# AGENTS.md — ThaiData UK

Repo for thaidata.uk, a static Thai-restaurant directory on Cloudflare Pages (auto-deploys on push to `main`).

## Hard rules

- **The whole repo root is published as-is.** Pages serves any committed file directly (static files beat `_redirects`, so blocking does not work — verified Oct 2026). Never commit anything internal unless it can be public: docs/, tests/, scripts/, analysis/ and .hermes/ are all reachable on the live domain. Secrets go in `secrets/` (gitignored, never committed). If an internal file must never be public, it must not be committed.
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
