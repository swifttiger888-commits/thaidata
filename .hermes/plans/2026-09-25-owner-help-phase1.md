# Proposal: Owner-help layer + corrections channel — Phase 1

**Status:** Awaiting approval — nothing built. Plan only.
**Date:** 2026-09-25
**Goal:** Make it easier for restaurant owners to reach ThaiData and act — more claims, fewer free-form support emails.
**Decided inputs (Johnny, 25 Sep):** audience = restaurant owners (claims & corrections); reply SLA = hours; outcome = more claims, fewer support emails.

No AI, no third-party chat, no cookies, no new dependencies. This layer is the substrate a Phase 2 assistant would sit on.

---

## 1. Current state — verified facts

| Fact | Detail |
|---|---|
| Contact channel | `hello@thaidata.uk` mailto only (footer + claim page). No on-site form except the homepage waitlist. |
| Claim funnel | `/claim/` page: search → details → submit. `?restaurant=` auto-searches (`prefillFromQuery`, claim/index.html ~345). `POST /api/claim` → D1 `claims` + Resend emails + Telegram ping (claim.js). |
| Missed context | Sidebar claim card link is `/claim/?src=restaurant-card` — no restaurant/city params, so the owner retypes the name (highest-friction funnel step). Hero CTA is just an anchor (`#claim`). Precedent for passing context exists: `build_menu_page.py` emits `?restaurant=&city=`. |
| Corrections | No mechanism. Corrections arrive as free-form email — unstructured, unrecorded, no dedupe. |
| /r/ pages | 1,289 generated pages. Template `templates/restaurant.html`; generator `scripts/generate_restaurant_pages.py`. Sidebar: claim card (`#claim`, template ~1170), claimed badge (`#claimed-badge`, ~1181). Client JS `enrichListing` (~1312–1657) hides the claim card when owner data exists. |
| Plumbing | Resend via `functions/api/_email.js` (`ADMIN_EMAIL` reply-to), Telegram helper local to claim.js, GA4 events (`claim_search`, `claim_submitted` with `src` attribution). `diag.js` reports env presence. |
| Safety rails | `ci_typecheck.py` runs `node --check` over `functions/**/*.js`. Runtime `CREATE TABLE IF NOT EXISTS` precedent (`email_log`, `login_attempts`). Rate-limit precedent: admin.js (5 attempts / 15 min / IP). |
| Privacy gap | privacy.html §1 lists only email-capture; §6 third parties = GA4, Clarity, Cloudflare, Google Fonts. Claims data, corrections data, Resend and Telegram are NOT listed. This work must close that gap. |
| D1 | `thaidata-db` (id `1905002a-1739-4a06-b6c2-f08d1c0d77a8`), binding `DB`. |

---

## 2. Deliverables

| # | Deliverable | Type |
|---|---|---|
| A | Claim links carry restaurant context; claim card answers 3 recurring questions | Template + generator |
| B | "Spotted a mistake?" report card on /r/ pages | Template + generator + inline JS |
| C | `POST /api/correction` + D1 `corrections` + notifications (Telegram, admin email, optional reporter ack) | Pages Function + `_email.js` |
| D | Privacy policy additions (claims, corrections, Resend, Telegram) | privacy.html |

---

## 3. A — Claim CTA de-friction

### A1. Sidebar card link (template ~1174 → generator)

Template keeps `href="/claim/?src=restaurant-card"`; the generator adds one replace in the claim_link block (~line 709):

```python
from urllib.parse import quote   # new top-level import
...
old = '<a href="/claim/?src=restaurant-card" class="btn">'
new = (f'<a href="/claim/?restaurant={quote(name)}&city={quote(city)}'
       f'&fsa_id={str(fsa_id)}&src=restaurant-card" class="btn">')
assert html.count(old) == 1, 'claim card link drifted'
html = html.replace(old, new)
```

### A2. Hero CTA (template ~1012)

Replace the anchor target only (keep the styling/text), in the non-closed branch:

```python
html = html.replace(
    '<a href="#claim"',
    f'<a href="/claim/?restaurant={quote(name)}&city={quote(city)}&fsa_id={str(fsa_id)}&src=hero-claim"',
)
```

Notes:
- Claim page needs no change: `?restaurant=` auto-searches. `city` is currently ignored (harmless); `fsa_id` is not consumed yet (kept for a future exact-match; harmless).
- `fsa_id` passed as a string — known D1 float pitfall (see claim-workflow skill).

### A3. Claim card: three self-serve answers

Add to the bottom of `.claim-card` (after the CTA + example link — button first, reassurance microcopy after, per the site's CTA conventions), three native `<details>` (no JS):

1. **Is it free?** — "Yes — claiming and managing your listing is free. ThaiData is a directory of UK Thai restaurants built on official FSA data."
2. **What can I add?** — "Photos, description, opening hours, website, social links, menu highlights, features and price range."
3. **How long does approval take?** — "Usually within 48 hours — we check you're connected to the restaurant first."

Copy mirrors the claim page FAQ (canonical wording lives there; keep both in sync).

CSS: ~8 lines (details/summary styling + chevron), alongside existing claim-card styles (~line 554).

---

## 4. B — Report card ("Spotted a mistake?")

### B1. Markup

New sidebar card after the claim card, before `#claimed-badge`, wrapped in a DYNAMIC region:

```html
<!-- DYNAMIC: report_card -->
<div class="card report-card" id="report-card">
    <h3>Spotted a mistake?</h3>
    <p>Know something that's wrong or out of date? Tell us — we check every report before changing anything.</p>
    <details id="report-details">
        <summary>Report an error <i class="fas fa-chevron-down"></i></summary>
        <form id="report-form" novalidate>
            <input type="text" name="website" class="hp-field" tabindex="-1" autocomplete="off" aria-hidden="true">
            <label for="report-category">What's wrong?</label>
            <select id="report-category">
                <option value="hours">Opening hours</option>
                <option value="address">Address or location</option>
                <option value="contact">Phone or website</option>
                <option value="closed">Permanently closed</option>
                <option value="menu">Menu or prices</option>
                <option value="other">Something else</option>
            </select>
            <label for="report-details-text">Details</label>
            <textarea id="report-details-text" rows="4" minlength="10" maxlength="2000"
                placeholder="e.g. We now open at 5pm on Sundays — the page says 12pm."></textarea>
            <label for="report-email">Your email (optional — only if you want a reply)</label>
            <input type="email" id="report-email" maxlength="254">
            <button type="submit" class="btn">Send report</button>
            <p id="report-status" role="status" style="display:none;"></p>
            <p class="report-fallback">Prefer email? <a href="mailto:hello@thaidata.uk">hello@thaidata.uk</a></p>
        </form>
    </details>
</div>
<!-- DYNAMIC: report_card_end -->
```

### B2. Client JS (same inline `<script>`, after enrichListing IIFE ~1657)

- Add `const RESTAURANT_FSA_ID = '0000000';` next to `RESTAURANT_NAME`/`RESTAURANT_CITY` (~1274) — the generator substitutes it.
- New IIFE (~45 lines): on submit, build payload
  `{restaurant_name, city, fsa_id: RESTAURANT_FSA_ID, category, details, reporter_email, website: honeypot, page_url: location.pathname}`,
  `fetch('/api/correction', POST JSON)`. Outcomes:
  - 201 → replace form with "Thanks — report received. A human checks every report, usually within a few hours."
  - 429 → "Too many reports from this connection right now. Try again later, or email hello@thaidata.uk."
  - other/network → retry message. Button disabled while in flight.
  - GA4: `correction_open` (details toggle), `correction_submit` (success; category included).
- Extend `enrichListing`'s "owner data" branch (~1331) to also hide `#report-card` (the claim card is hidden there today; same rule applies).

### B3. Generator handling

- Replace `const RESTAURANT_FSA_ID = '0000000';` with `str(fsa_id)`.
- Open pages: strip `<!-- DYNAMIC: report_card -->` and `<!-- DYNAMIC: report_card_end -->` marker lines.
- Closed pages (`is_closed`): remove the whole region via `safe_sub(r'<!-- DYNAMIC: report_card -->.*?<!-- DYNAMIC: report_card_end -->\s*', '', html)` — report entry is not offered on closed pages.
- Add a final assertion: `'DYNAMIC' not in html` (current output already satisfies this; fails loudly if a marker is missed).

### B4. CSS (~15 lines)

`.hp-field { position:absolute; left:-9999px; }`, summary/label/status styling. Container reuses `.card`.

---

## 5. C — `POST /api/correction` (functions/api/correction.js)

### Validation

| Field | Rule | Fail |
|---|---|---|
| restaurant_name | required, 1–200 chars | 400 |
| city | required, 1–100 | 400 |
| fsa_id | optional, ≤20, cast to string | ignored |
| category | required, one of `hours/address/contact/closed/menu/other` | 400 |
| details | required, trimmed 10–2000 chars | 400 |
| reporter_email | optional, email regex, ≤254 | 400 |
| website (honeypot) | must be empty | silent 200 `{success:true}` — no insert, logged |
| page_url | optional, ≤300 | ignored |

Rate limit: 5 per hour per IP (`CF-Connecting-IP`), `correction_attempts` table (admin.js `login_attempts` pattern; prune rows older than 1 hour on each request) → 429.

### DDL (runtime `CREATE TABLE IF NOT EXISTS` in the handler + mirrored in schema.sql)

```sql
CREATE TABLE IF NOT EXISTS corrections (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fsa_id TEXT,
  restaurant_name TEXT NOT NULL,
  city TEXT NOT NULL,
  category TEXT NOT NULL,
  details TEXT NOT NULL,
  reporter_email TEXT,
  page_url TEXT,
  status TEXT NOT NULL DEFAULT 'new',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS correction_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ip TEXT NOT NULL,
  attempted_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### Behaviour

1. Parse + validate (JSON body; CORS `*` headers as in claim.js).
2. Insert → id.
3. Notify via `Promise.allSettled` (never blocks or fails the response — claim.js pattern):
   - Telegram ping — small local helper in correction.js (claim.js has its own local helper; this PR deliberately does not touch claim.js — see §9).
   - Admin email via new `sendCorrectionNotification` (`reply_to` = reporter's email when given, so replying goes straight to the reporter).
   - Reporter ack via new `sendCorrectionAck` (only when an email was provided).
4. 201 `{success:true, id}`.

**No auto-edits.** Reports land as `status='new'`. Data changes remain human-reviewed; "permanently closed" changes continue to go through the existing closed-list pipeline, never directly from a report.

---

## 6. D — Email helpers (_email.js additions)

- `sendCorrectionNotification(env, {id, restaurant_name, city, category, details, reporter_email, page_url})` → to `ADMIN_EMAIL` (hello@ fallback); subject `Correction report — {name} ({city}) — {category}`.
- `sendCorrectionAck(env, {to, restaurant_name})` → subject `We've got your report — {restaurant_name}`; sets expectation ("A human checks every report"). Both route through the existing `sendEmail()` (writes `email_log`).

---

## 7. E — Privacy policy additions (privacy.html)

- §1 "Information we collect": bullets for claims (name, email, optional phone — to verify and set up the listing) and corrections (message, optional email, page URL, IP for spam prevention).
- §4 retention: correction reports reviewed then deleted after 12 months; spam-prevention IPs discarded within an hour.
- §6 third parties: add **Resend** (email delivery) and **Telegram** (admin notifications).

---

## 8. Tests

### `tests/test_correction_api.mjs` (new, offline)

Harness: import `correction.js` via data: URL with the `./_email.js` import rewritten to its own data: URL (same trick as `test_middleware_photos.mjs`); mock DB recorder (capture prepare/bind/run/first/all) + fetch stub.

1. missing required fields → 400
2. bad category → 400
3. details < 10 chars → 400
4. bad reporter email → 400
5. honeypot filled → 200, no INSERT issued
6. valid submission → 201; `INSERT INTO corrections` with expected binds; notification attempted
7. 6th submission in window → 429
8. notification fetch throws → still 201

Run: `node tests/test_correction_api.mjs`

### `tests/test_owner_help_static.py` (new, offline — reads repo files)

Samples: `r/leeds/my-thai/index.html` (open), `r/leeds/thai-edge/index.html` (closed).

- Open: contains `href="/claim/?restaurant=My%20Thai&city=Leeds&fsa_id=`; contains `id="report-card"`; `RESTAURANT_FSA_ID` matches the `thaidata:fsa-id` meta; no `DYNAMIC` markers anywhere in the file.
- Closed: no `report-card`, no claim card; closed notice present.

Run: `python3 -m pytest tests/test_owner_help_static.py -v`

### Gates

- `python3 scripts/ci_typecheck.py` (auto-covers correction.js via `node --check`)
- `node tests/test_middleware_photos.mjs` (expect unchanged; run to confirm)
- `python3 -m pytest tests` (offline subset)

---

## 9. Regen, deploy, verification

1. Edit template + generator + functions + privacy.html; regenerate: `python3 scripts/generate_restaurant_pages.py` (background; ~1,289 pages).
2. `git diff --stat` review — expect diffs confined to: template, generator, `functions/api/correction.js`, `_email.js`, `privacy.html`, `schema.sql`, `tests/*`, and `r/**/index.html` (sidebar/hero/JS-const areas only). Spot-check one full page diff.
3. Run tests + CI gates.
4. Optionally pre-create the D1 tables (`wrangler d1 execute thaidata-db --remote --command "..."`) — otherwise the first submission creates them (email_log precedent).
5. Push → Pages auto-deploy. Verify:
   - `curl -s "https://thaidata.uk/r/leeds/my-thai/?cb=$(date +%s)"` → params + report card present.
   - POST a test report (details marked "TEST — please ignore") → expect Telegram ping, hello@ email, ack email; row confirmed via `wrangler d1 execute thaidata-db --remote --command "SELECT id, restaurant_name, category, status, created_at FROM corrections ORDER BY id DESC LIMIT 3"`.
   - GA4 DebugView: `correction_submit` fires; claim links carry `src`.
6. Measurement (2-week review): claim starts by src (restaurant-card / hero-claim / menu-page / footer), report volume + mix, hello@ volume.

---

## 10. Risks, decisions, open questions

**Risks**
- Template change multiplies across 1,289 pages → marker assertion + static tests + single-page diff review. Rollback: revert commit, redeploy.
- New public POST → honeypot + throttle; optional Cloudflare rate-limit rule on `/api/correction` (dashboard).
- Reporter ack can bounce (fake addresses) — logged, ignored.
- Nothing is ever auto-edited from a report.

**Decisions made in this plan (flag if you disagree)**
- Reporter ack email: included.
- Admin notification `reply_to` = reporter's email.
- No report card on claimed pages in Phase 1 (owners manage their own data; "closed" reports from claimed pages still arrive by email).
- Report retention: 12 months (privacy wording, §7).

**Open questions**
1. Wording of the three claim-card answers — happy with the drafts in §3.3?
2. Should a "permanently closed" report do more than land in D1 + notify (e.g. a review queue)? Proposal: no in Phase 1; the closed list stays pipeline-managed.

**Not in scope (Phase 2+):** AI assistant (EN/Thai), Turnstile, ticketing/status UI, report card on claimed pages, WhatsApp.
