# Owner Claims Growth Plan

**Written:** 2026-08-12 · **Owner:** thaidata.uk
**Purpose:** A file-scoped, sequenced task list any capable model/agent can execute
without re-deriving context. Each task has a target file, exact change, and an
acceptance check. Execute phases in order; tasks within a phase are independent
unless noted.

---

## Diagnosis (read this before executing anything)

GA4 export (2026-07-15 → 2026-08-11, 28 days):

| Metric | Value |
|---|---|
| Active users (whole site) | 23 |
| Direct traffic share | 21 of 23 |
| Google organic users | **1** |
| `/claim/` pageviews | 4 (3 users) |
| Top "city" | Ashburn, VA (datacenter → bots/monitoring) |

**Conclusion: this is an acquisition problem, not a conversion problem.**
Zero claims from ~3 claim-page visitors is the expected outcome at this volume.
A 1,269-page site receiving 1 organic visitor/month means Google is sending
essentially nobody. Any conversion-rate work is polish until owners actually
reach the site — so the highest-leverage phase is direct outreach (Phase 1),
which needs no traffic at all: the repo already holds contact data for the
restaurants themselves (`data/google_enrichment.json`: 1,107 websites, 1,195
phone numbers, postal addresses for all 1,269).

**Already done (2026-08-12, branch `claude/thaidata-restaurant-claims-c3t0pj`):**
- `claim/index.html`: pre-selects the restaurant when arriving with
  `?rid=<fsa_id>&rname=<name>` (skips the search step); confirm-email field
  removed; "Be among the first…" anti-social-proof line replaced with a
  benefits line.
- `scripts/generate_restaurant_pages.py`: restaurant-card claim links now emit
  `/claim/?src=restaurant-card&rid=<fsa_id>&rname=<urlencoded name>`.
  Generated pages under `r/` pick this up on the next pipeline run — do NOT
  hand-edit files under `r/`.

**Repo conventions the executor must respect:**
- Pages under `r/` and `cities/` are GENERATED. Change the generators in
  `scripts/` (template for `r/` pages: `r/leeds/my-thai/index.html`), never the
  output. An external "Hermes Agent" auto-refresh job regenerates and commits.
- Verify any change with: `python scripts/ci_typecheck.py` and
  `python -m pytest tests/ -v` (88 tests; all pass as of this commit).
- Claim funnel GA4 events already instrumented: `claim_search`, `claim_select`,
  `claim_submitted` (with `claim_source` from `?src=`). Keep them working.
- `/api/claim` (Cloudflare Pages function `functions/api/claim.js`) already
  sends claimant confirmation + admin notification emails via
  `functions/api/_email.js`. Review is manual via `admin.html`, ~48h SLA.

---

## Phase 0 — Human-only prerequisites (site owner, ~30 min, no code)

These cannot be done by the executing model. Do them first; Phase 3 depends on P0.2.

- **P0.1** In GA4: Admin → Data Settings → Data Filters — define internal
  traffic (your own IP) and activate the filter. Ashburn/datacenter noise
  can't be filtered retroactively, but going forward mark `claim_submitted`
  as a key event (Admin → Events → toggle "Mark as key event").
- **P0.2** In Google Search Console (add property if missing): record
  (a) pages indexed vs. discovered-not-indexed under Indexing → Pages,
  (b) top 20 queries by impressions. Paste both into a new file
  `docs/gsc-snapshot-2026-08.md`. Phase 3 branches on this data.
- **P0.3** Decide the outreach sender identity (name + reply-to on
  hello@thaidata.uk) and whether a small print budget (~£150–300 for
  postcards) exists. Record the decision in this file under P0.3.

---

## Phase 1 — Direct outreach engine (the lever; do this before any SEO work)

Goal: put the claim link in front of 1,269 owners directly instead of waiting
for search traffic. Everything below is buildable offline from repo data.

- **T1.1 — Build the outreach master list.**
  New script `scripts/build_outreach_list.py`. Read `data/restaurants.json`
  (fields: id, name, address, city, postcode, …) joined with
  `data/google_enrichment.json` on `fsa_id` (fields incl. website, phone,
  rating, review_count). Exclude ids present in `data/closed_venues.json` and
  `data/exclusions.json`. Output `data/outreach/outreach_list.csv` with
  columns: `fsa_id, name, address, city, postcode, phone, website,
  listing_url, claim_url, google_rating, review_count`, where
  `listing_url = https://thaidata.uk/r/<city_slug>/<name_slug>/` (reuse the
  slug functions from `scripts/generate_restaurant_pages.py` — import them,
  don't reimplement) and
  `claim_url = https://thaidata.uk/claim/?src=<CHANNEL>&rid=<fsa_id>&rname=<urlencoded name>`
  with `<CHANNEL>` left as a literal `{src}` placeholder for the mail-merge
  step. Add `data/outreach/` to `.gitignore`? No — commit the CSV; it contains
  only public business data.
  *Accept:* CSV has ≥1,200 rows; spot-check 3 `listing_url`s resolve to real
  files under `r/`; script is idempotent.

- **T1.2 — Scrape contact emails from restaurant websites (careful task).**
  New script `scripts/find_owner_emails.py`: for each row with a `website`,
  fetch the homepage + likely contact pages (`/contact`, `/about`) with a
  10s timeout and a descriptive User-Agent (`ThaiDataUK-outreach/1.0
  (+https://thaidata.uk; hello@thaidata.uk)`), extract `mailto:` and visible
  email addresses, and write `email, email_source_url` columns back into the
  CSV. Rate-limit ≥2s between requests; skip on any robots.txt disallow; one
  retry max. UK PECR note for the human: emailing corporate addresses
  (info@restaurant…) about their own listing is legitimate B2B contact, but
  every send must identify the sender and include a working opt-out; keep an
  unsubscribe list at `data/outreach/optout.csv` and honour it in T1.4.
  *Accept:* script runs to completion without hammering any host; report %
  of rows with an email found.

- **T1.3 — Claim incentive: per-city competitor snapshot.**
  The claim offer today ("add photos and hours") is weak. The repo already
  computes price/hygiene data (`thai-menu-price-index-uk.html`,
  `data/restaurants.json`, mockup in `thaidata_free_report_mockup.jpg`).
  New script `scripts/generate_city_reports.py`: for each city with ≥5
  restaurants, render a one-page HTML report (count of Thai restaurants,
  hygiene-rating distribution, the restaurant's own rating vs. city average)
  to `reports/<city_slug>/index.html`, linked from the claim confirmation
  screen and mentioned in outreach copy ("claim your listing and get the
  free <City> Thai restaurant report"). Keep the page static, no JS deps,
  reuse site CSS vars.
  *Accept:* reports exist for the top 20 cities; claim confirmation section in
  `claim/index.html` links to the claimant's city report when the slug exists.

- **T1.4 — Outreach copy pack.**
  New file `docs/outreach/templates.md` containing: (a) a 90-word email
  (subject ≤45 chars, one link = the row's `claim_url` with `src=email`,
  opt-out line), (b) an A6 postcard layout brief with QR code
  (`src=postcard`), (c) a 3-sentence Instagram/Facebook DM (`src=dm`),
  (d) a 20-second phone script (`src=phone`). Voice: "Your restaurant is
  already listed — 2 minutes to take control of it." Mention the FSA data
  source (it's why the listing exists) and the free city report (T1.3).
  New script `scripts/generate_qr_codes.py` producing per-restaurant QR SVGs
  into `data/outreach/qr/` using the `segno` package (add to
  `requirements.txt`; pure-Python, no system deps).
  *Accept:* templates render with a sample row without leftover `{placeholders}`;
  QR SVGs scan to the correct claim_url (validate by decoding 3 samples with
  `segno`/`zbar` or by URL-parsing the generated payload).

- **T1.5 — Channel tracking.**
  `claim/index.html` already forwards `?src=` into the GA4 `claim_submitted`
  event. Extend `functions/api/claim.js` to also persist the source: add a
  nullable `claim_source` column (migration in `schema.sql` + `ALTER TABLE`
  note in the PR description), read `body.claim_source`, and pass it from the
  front-end submit payload (`new URLSearchParams(location.search).get('src')`).
  *Accept:* pytest green; submitting with `?src=postcard` stores
  `claim_source='postcard'`.

---

## Phase 2 — Convert the owner traffic the site already gets

The content library (cost guides, calculators, wage reports) is owner-bait,
and the GA4 top page is owner-facing — but **zero owner-facing tool/report
pages link to /claim/**. Fix that.

- **T2.1 — Claim banner on owner-facing pages.**
  Add one consistent banner component (inline HTML/CSS block, no JS) directly
  under the `<h1>`/hero of each file below, linking to
  `/claim/?src=owner-tools`. Copy: "Own a Thai restaurant? Your listing is
  already on ThaiData — claim it free in 2 minutes." Files (root):
  `nlw-report.html, thai-restaurant-gp-calculator.html,
  thai-restaurant-costs-uk.html, thai-menu-price-index-uk.html,
  thai-restaurant-revenue-benchmarks-uk.html, thai-restaurant-marketing-uk.html,
  open-thai-restaurant-uk.html, open-thai-restaurant-timeline-uk.html,
  thai-restaurant-menu-pricing-uk.html, thai-restaurant-delivery-commissions-uk.html,
  thai-wholesale-suppliers-uk.html, thai-chef-visa-uk.html, tools.html` and
  every page in `tools/` (~22 files). Respect
  `docs/cta-link-accessibility-guidelines.md` and
  `docs/mobile-layout-contrast-guidelines.md`.
  *Accept:* `grep -L '/claim/?src=owner-tools' <those files>` returns empty;
  banner passes the contrast guideline; pages remain valid per
  `scripts/ci_typecheck.py`.

- **T2.2 — Homepage title/positioning mismatch (needs a human decision).**
  `index.html` has `<title>Free Minimum Wage Calculator for UK Thai
  Restaurants…</title>` while its H1 is "Your restaurant is already on
  ThaiData". Recommended: retitle to
  `ThaiData UK — Every Thai Restaurant in the UK, Verified` (title, og:title,
  twitter:title). **Ask the site owner before changing** — the calculator
  title may be a deliberate SEO experiment.

- **T2.3 — Demo listing link integrity.**
  `claim/index.html` links to `/r/demo/claimed-listing/`. Verify that path
  exists in the repo; if not, point it at a real claimed example or build the
  demo page. *Accept:* link returns a page in local repo tree.

---

## Phase 3 — Indexing & SEO (only after P0.2 data exists)

Branch on the GSC snapshot:
- If most `r/` pages are "Discovered – not indexed": likely crawl-budget/quality
  signals. Tasks: strengthen internal linking (T3.1), verify
  `sitemap.xml` index references both child sitemaps and that
  `scripts/ping_indexnow.py` runs in the pipeline (recent commit history shows
  sitemap fixes — confirm live behaviour), and delete the stray
  `sitemap.xml.clean` from the repo root if unused.
- If pages are indexed but get no impressions: the pages target zero-volume
  queries; prioritise city hubs over individual listings.
- **T3.1 — Internal linking:** every `r/` page links to its city hub (exists);
  ensure city hubs link to ALL their restaurants (check
  `scripts/generate_city_hub.py` pagination/truncation) and that root pages
  (`index.html`, `restaurants.html`) link to all city hubs.
- **T3.2 — llms.txt freshness:** `llms.txt`/`llms-full.txt` exist; keep the
  claim CTA and counts current (one GA4 session already came from an AI
  assistant — copilot.com).

---

## Phase 4 — Measure (2 weeks after first outreach batch)

Success metric: **claims submitted per outreach channel** (D1 `claim_source`
column from T1.5 + GA4 `claim_submitted` by `claim_source`). Guardrails: FSA
data pipeline stays green; no growth in bounce complaints to hello@thaidata.uk.
Kill/scale rule: a channel that produces 0 claims after 200 contacts is dead;
double down on any channel with ≥2% claim rate.

---

## Explicit non-goals for the executor

- No paid ads setup, no social account creation, no scraping beyond T1.2's
  polite single-pass email finder.
- No redesign of the claim page or listing pages; conversion polish beyond
  the shipped fixes is deferred until there is measurable funnel volume.
- Never commit secrets; email sending stays manual (mail-merge by the human)
  until volumes justify automation.
