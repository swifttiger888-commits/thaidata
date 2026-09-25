# Menu-page batch — plan (2026-09-25)

## Why
GSC: "<name> menu" queries = 1,000+ impressions/28d across 68 pages, ~3 clicks
total (positions 7–12). Where a real menu page exists, it does better (woburn
menu 7.1% CTR @ pos 4.6 vs listing pages at ~0%). Talay (Porthleven) alone
carries 327 menu-query impressions at 0 clicks.

## What exists
- 25 menu pages under `r/<city>/<slug>/menu/` (data: `data/menus/*.json`).
- `scripts/build_menu_page.py menu.json r/<city>/<slug>/menu/index.html` — schema
  documented in its docstring (source URL + source_label + checked date required).
- `scripts/generate_sitemaps.py::discover_menu_pages()` auto-adds new menu pages
  to `sitemap-r-restaurants.xml`.
- Menu pages link back to their listing; **listings do NOT link to menus**
  (one-way). Optional wiring fix below.

## Proposed batch (ranked by menu-query demand)
| # | Venue | Listing | Menu-query imp (28d) | Source status |
|---|-------|---------|----------------------|---------------|
| 1 | Talay Thai (Porthleven) | /r/cornwall/talay-thai/ | ~327 | Brand PDF on talay.co.uk — verify it covers Porthleven before reuse |
| 2 | Ran Thai | /r/london/ran-thai-restaurant/ | ~170 | To find (own site) |
| 3 | Brother Thai | /r/bristol/brother-thai/ | ~122 | brotherthai.co.uk ✓ |
| 4 | Araya Thai | /r/lincoln/araya-thai-restaurant/ | ~118 | To find |
| 5 | BKK Thai Takeaway | /r/cheshire-east/bkk-thai-takeaway/ | ~90 | To find |
| 6 | Thai Corner | /r/neath-port-talbot/thai-corner-limited/ | ~49 | To find |
| 7 | Nannapat | /r/sefton/nannapat-thai-restaurant-bar/ | ~48 | To find |
| 8 | Thai Box | /r/shropshire/thai-box/ | ~48 | To find |

Rule: if a venue's own menu can't be located/verified, swap in the next
candidate (noi's thai 44, orange thai 43, nat's pad thai 37) — never aggregator
menus as the primary source.

## Method per venue (review-first)
1. Locate the venue's OWN menu (website / PDF). Record source URL.
2. Extract items+prices into `data/menus/<slug>-<city>.json` per the
   build_menu_page.py schema. Missing data = omit; never estimate.
3. Review: spot-check 5+ items against the source; confirm source_label +
   checked date.
4. Build page; verify live; confirm sitemap discovery on next `generate_sitemaps.py` run.

## Optional wiring fix (separate decision)
Add a "View full menu" link from listing pages to their menu page when one
exists (template + generator edit, one regen). Currently menu pages get no
internal link equity from their listings.

## Risks
- Staleness: checked date is shown; claim flow lets owners correct.
- Copyright: menu names/prices are facts; keep descriptions short (house style
  matches existing 25 pages); always attribute + link the source.
- Source rot: if a source disappears later, page keeps its checked date.

## Sequence
Pilot talay Porthleven (verify brand-PDF coverage first) → review with Johnny →
then the rest in batches of 2–3 with the same gates.

## Status
- 2026-09-25: PILOT DONE — Talay Thai Porthleven menu published (commit `2c5d38b2c`):
  61 items / 9 categories, extracted from the venue's own click & collect menu
  (session-gated touchtakeaway platform — CDP harness; see
  thaidata-aeo-roadmap/references/menu-pages.md). Sitemap auto-discovery verified.
- Batch addition: talay-thai-kitchen (St Ives) menu prices render without £ (bare
  numbers in its JSON) — fix when touching that file.
- 2026-09-25 (batch done): Brother Thai (Bristol) 24 items + Araya Thai (Lincoln)
  82 items published (38d39ab5a, 6e4ba24ab). Remaining candidates: Ran Thai,
  BKK Thai, Thai Corner (Neath), Nannapat, Thai Box.
- 2026-09-25 (batch 2 done): Thai Box (Ludlow) 100 items (7978b97fb); BKK Thai
  (Macclesfield) 83 items (09666d674). Bonus: £-price sweep across 9 older menu
  pages — 264 bare prices fixed + pages rebuilt (11f742ff1). Site now has 28
  menu pages.
- Deferred (platform-gated, need bespoke extraction): Ran Thai (Hanwell — Facebook
  + Patato QR app only), Nannapat (Maghull — Lightspeed ordering app), Thai Corner
  (Neath — Square Online product pages).
