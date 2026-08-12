# Owner Claims Growth Plan

**Written:** 2026-08-12 · **Owner:** thaidata.uk
**Purpose:** A file-scoped, sequenced task list executed by lightweight agents
(e.g. DeepSeek v4 flash / v4 pro on Hermes). Each task has a target file, exact
change, and an acceptance check. Execute phases in order; tasks within a phase
are independent unless the Task Index says otherwise.

---

## Execution protocol — every agent reads this first, every run

1. **Pick ONE task** from the Task Index below whose Status is `TODO`, whose
   dependencies are `DONE`, and whose Tier matches your model (`flash` tasks
   may also be done by `pro`; never the reverse).
2. Set its Status to `IN PROGRESS` in the Task Index (commit this with your
   work, not separately).
3. Do **only** what the task specifies. If the task is ambiguous, or its
   acceptance check cannot be met, set Status to `BLOCKED: <one-line reason>`
   and stop — do not improvise, broaden scope, or "fix" neighbouring code.
4. Before committing, run ALL of:
   - `python -m pytest tests/ -q` (must stay at 88 passed)
   - `python scripts/ci_typecheck.py` (must print all-pass)
   - `node --check` on any inline `<script>` you edited (extract to a temp
     file first)
5. Commit with message `T<id>: <what changed>` and set Status to `DONE` in the
   same commit. One task per commit. Keep the diff minimal — no reformatting,
   no dependency upgrades, no drive-by changes.

**Hard rules (violating any of these = failed task):**
- NEVER edit files under `r/` or `cities/` — they are generated. The only
  exception is `r/leeds/my-thai/index.html` (the template) when a task names
  it explicitly. Page-level changes go in `scripts/generate_*.py`.
- NEVER edit `data/thai_fsa_latest.json`, `sitemap*.xml`, `feed.json`, or
  anything under `.wrangler/` — pipeline-owned.
- NEVER commit secrets, tokens, or `.env` values. `wrangler.toml` stays as-is.
- NEVER invent facts that will be shown to humans: no fabricated statistics,
  testimonials, staff names, or company details. If a task needs content only
  the site owner knows, it is `BLOCKED` until they supply it.
- NEVER send email, post to social media, or contact any restaurant. Agents
  build artifacts (CSVs, templates, QR codes); a human sends everything.
- GA4 events `claim_search` / `claim_select` / `claim_submitted` must keep
  firing after any claim-page change.

## Task Index & routing

Tier meaning: `flash` = mechanical, fully specified, low-judgement.
`pro` = multi-file reasoning, parsing, or security-sensitive.
`human` = only the site owner can do it. Update Status in place.

| ID   | Summary                                   | Tier  | Depends on | Status |
|------|-------------------------------------------|-------|------------|--------|
| P0.1 | GA4 filters + key event                   | human | —          | TODO |
| P0.2 | GSC snapshot → docs/gsc-snapshot-2026-08.md | human | —        | TODO |
| P0.3 | Sender identity + print budget decision   | human | —          | TODO |
| P0.4 | SPF/DKIM/DMARC verified on thaidata.uk    | human | —          | TODO |
| T1.1 | Outreach master CSV                       | flash | —          | TODO |
| T1.2 | Email finder script (polite, single-pass) | pro   | T1.1       | TODO |
| T1.3 | Per-city report pages (claim incentive)   | pro   | —          | TODO |
| T1.4 | Outreach copy pack + QR code script       | pro   | T1.1, P0.3 | TODO |
| T1.5 | Persist claim_source in D1                | pro   | —          | TODO |
| T2.1 | Claim banners on ~35 owner-facing pages   | flash | —          | TODO |
| T2.2 | Homepage title fix                        | flash | P0 decision by owner | BLOCKED: owner decision |
| T2.3 | Build /r/demo/claimed-listing/ (404 now)  | pro   | —          | TODO |
| T2.4 | "Who runs ThaiData" trust section         | flash | P0.3       | TODO |
| T2.5 | Post-approval flow review (manage.html)   | pro   | —          | TODO |
| T2.6 | Security pass on admin surfaces           | pro   | —          | TODO |
| T2.7 | Listing page: enrichment-led redesign     | pro   | —          | TODO |
| T2.8 | Homepage: cut to router page              | pro   | T2.2 for title only | TODO |
| T3.1 | Internal linking audit                    | pro   | P0.2       | TODO |
| T3.2 | llms.txt freshness                        | flash | —          | TODO |

Recommended order: T2.1 → T1.1 → T1.5 → T2.3 → T1.3 → T1.2 → T1.4 (needs
P0.3), with T2.6 done before any outreach is actually sent. Phase 3 waits
for P0.2 data.

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
- `claim/index.html` search now queries `/api/search-restaurants` (curated
  local index) first, falling back to `/api/search` (live FSA proxy) only
  when the index has no match. Rationale: the FSA proxy's Thai-keyword name
  filter made **90 of 1,269 listed restaurants unfindable** in claim search
  (e.g. the entire Banana Tree chain).
- Scottish rating rendering fixed in `generate_restaurant_pages.py`: FHIS
  text outcomes ('Pass', 'Improvement Required', 'Exempt' — 56 venues) no
  longer break the 0–5 rating circle or render as nonsense like
  "FSA Improvement Required/5" in titles/badges/meta; they get a colour pill,
  an FHIS explainer label, and a corrected footnote. '0' ratings mapped
  correctly. `REPO` is now overridable via the `THAIDATA_REPO` env var so the
  generator can run outside the Hermes container:
  `THAIDATA_REPO=$PWD python scripts/generate_restaurant_pages.py`.

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
- **P0.4** Email deliverability: verify SPF, DKIM and DMARC records exist for
  thaidata.uk (e.g. via your DNS host or `dig txt thaidata.uk`). Outreach
  email (T1.4) MUST NOT be sent until these pass — cold mail without them
  lands in spam and can burn the domain's reputation.

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
  Use this exact markup — pick the variant matching the page's background
  (inspect the page's `body` background color; light page → light variant):

  ```html
  <!-- light pages -->
  <div style="background:#ECFDF5;border:1px solid rgba(16,185,129,0.35);border-radius:12px;padding:14px 20px;margin:20px 0;font-size:0.95rem;color:#065F46;">
    <strong>Own a Thai restaurant?</strong> Your listing is already on ThaiData —
    <a href="/claim/?src=owner-tools" style="color:#0A7A6F;font-weight:700;">claim it free in 2 minutes &rarr;</a>
  </div>
  <!-- dark pages -->
  <div style="background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.3);border-radius:12px;padding:14px 20px;margin:20px 0;font-size:0.95rem;color:#D1FAE5;">
    <strong>Own a Thai restaurant?</strong> Your listing is already on ThaiData —
    <a href="/claim/?src=owner-tools" style="color:#10B981;font-weight:700;">claim it free in 2 minutes &rarr;</a>
  </div>
  ```
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

- **T2.3 — Demo listing link is broken (confirmed).**
  `claim/index.html` links to `/r/demo/claimed-listing/`, which exists neither
  as a static file nor in `functions/r/_middleware.js` nor `_redirects` — the
  claim page's main persuasion link is a 404. Build the demo page: copy a real
  generated page from `r/`, rename to "Demo Thai Restaurant", and populate the
  claimed-state sections that the template hides for unclaimed listings
  (photos, description, hours — the CSS classes `claimed-badge` /
  `claimed-description` already exist in the template). Add
  `noindex` meta. *Accept:* the path resolves in the repo tree and shows
  visibly richer content than an unclaimed page.

---

- **T2.4 — "Who runs ThaiData" trust section.**
  Owners receiving cold outreach will look the site up before handing over
  name/email/phone. Add a short section to `about.html` (and a one-line
  footer credit site-wide via the generators) naming the person or company
  behind the site, with a reply-to human email. Content comes from the site
  owner (see P0.3) — the executor wires it in, never invents identity
  details. *Accept:* about.html names a real operator; claim page links to it.

- **T2.5 — Post-approval experience review.**
  `listing/manage.html` (941 lines) is what an owner reaches after approval.
  Walk the full flow against a claimed test record: token/link arrival email
  (`functions/api/_email.js`), every editable field saving via
  `functions/api/listing.js`, photo upload via `functions/api/upload.js`,
  and how the claimed listing then renders under `r/`
  (`functions/r/_middleware.js`). Fix what's broken; list what's merely
  rough in a follow-up section appended to this file.
  *Accept:* a test claim can be approved and its listing visibly updated
  end-to-end without touching the database by hand.

- **T2.7 — Listing page: lead with the restaurant, not the inspection.**
  Files: `r/leeds/my-thai/index.html` (template) +
  `scripts/generate_restaurant_pages.py`. Never edit generated pages; verify
  with `THAIDATA_REPO=$PWD python scripts/generate_restaurant_pages.py` then
  `git checkout -- r/` before committing (commit ONLY template + generator).
  Changes, all data-driven from `data/google_enrichment.json` (keyed by
  fsa_id; 1,249/1,265 records have `rating` + `review_count`):
  (a) Add a Google rating badge next to the FSA badge in the hero and in the
  hygiene card area: "★ 4.4 (145 Google reviews)", linked to
  `https://www.google.com/maps/place/?q=place_id:<google_place_id>` with
  visible "Google" attribution per Google Maps Platform attribution rules.
  Never fabricate a rating; omit the badge when enrichment has none.
  (b) Replace the boilerplate "At a Glance" sidebar items ("Thai Cuisine —
  Authentic flavours", "<City> — UK") with per-restaurant facts: Google
  rating, price level when present, venue type, and "1 of <N> Thai venues in
  <city>" computed from `data/restaurants.json`.
  (c) Fix the hero claim-line contrast: the light-green-on-green paragraph
  under the H1 must meet WCAG AA (4.5:1) against the hero gradient — check
  `docs/mobile-layout-contrast-guidelines.md`.
  (d) Style the "Explore More" related-links block as cards consistent with
  the page's card design (it is currently a bare link list).
  (e) Check the Google Maps `embed?pb=` iframe renders on the LIVE site
  (needs a human or an agent with network access); if broken, switch the
  generator to `https://maps.google.com/maps?q=<lat>,<lng>&output=embed`.
  *Accept:* regenerated sample pages (one English 5-rated, one Scottish
  'Improvement Required', one with no enrichment) render correctly;
  `python -m pytest tests/ -q` stays green; FSA data remains visible on
  every page (data integrity — do NOT hide bad hygiene ratings).

- **T2.8 — Homepage: cut to a router page (~75% shorter).**
  File: `index.html` (it is hand-authored, not generated). Today it is
  ~8,200px tall on desktop: an owner-pitch hero + an entire NLW cost article
  with an embedded multi-step calculator + a guides hub + inline FAQ + email
  capture + a mega tool list. Restructure to, in order:
  (1) Hero: H1 "Every Thai restaurant in the UK, verified" + one-line sub +
  two CTAs — "Find a Thai restaurant" → `/restaurants.html`, "Own one? Claim
  your free listing" → `/claim/?src=home`.
  (2) Proof strip: restaurant count, area count, "updated daily from FSA
  data" (compute counts from `data/restaurants.json`, don't hardcode).
  (3) Three route cards: Directory (cities index) / Owner tools (`/tools.html`)
  / Reports & data (`/state-of-uk-thai-food-2026.html`).
  (4) Compact guides row (top 4 guides max) + existing email capture.
  (5) Slim footer.
  The NLW article + calculator content must be RELOCATED, not deleted:
  the article duplicates `nlw-report.html` — diff them and merge anything
  unique into `nlw-report.html`; move the interactive calculator markup+JS
  to a new `tools/wage-cost-calculator.html` and link it from `tools.html`.
  Preserve: GA4 tag, canonical, `privacy-banner.js`, structured data, and
  the `<title>` decision from T2.2 (if still blocked, keep the current
  title text but complete the restructure).
  *Accept:* rendered full-page height at 1280px width is under 3,000px
  (measure with a headless browser or estimate by section count); every
  removed section is reachable via a link on the new page; all internal
  links resolve to files in the repo; `python scripts/ci_typecheck.py`
  passes.

- **T2.6 — Security pass on admin surfaces (before any outreach batch).**
  `admin.html`, `admin/`, `functions/api/admin.js` and
  `functions/api/admin/exclusions.js` are publicly served; their auth has
  not been audited. Review authn/authz on every admin and write endpoint
  (claims approval, exclusions, uploads, enrichment). Run the repo's
  security-review tooling if available. *Accept:* every state-changing
  endpoint verifiably rejects unauthenticated requests; findings and fixes
  noted in the PR that closes this task.

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
