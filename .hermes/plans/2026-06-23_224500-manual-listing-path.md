# Manual Listing Path for Non-FSA Vendors — Implementation Plan

> **For Hermes:** Use subagent-driven-development to implement this plan task-by-task.

**Goal:** Let Thai food vendors not in the FSA database (street stalls, festivals, market traders, pop-ups, new openings) submit listings and appear on thaidata.uk.

**Architecture:** Extend the existing claim form with a "manual entry" toggle. Bypass FSA autocomplete for these submissions, collect address manually, flag them in D1 with `fsa_id = null` + `source = 'manual'`. Admin approves with manual review (no FSA pre-fill). Serve pages via a new Cloudflare Pages Function at `/r/manual/{slug}/` that renders from D1 — no static generation needed.

**Tech Stack:** HTML/JS (claim form), Cloudflare Pages Functions (JS), D1 (SQLite), existing admin panel.

---

## Current State (Phase 1 — Read and Map)

### Files that control this feature

| File | Role |
|------|------|
| `claim/index.html` | Claim form UI — FSA autocomplete + submit |
| `functions/api/search.js` | `/api/search` → proxies FSA API, filters to Thai names. **Only source of restaurant data for the claim form.** |
| `functions/api/claim.js` | `POST /api/claim` — validates, checks duplicates, inserts claim, sends notifications |
| `functions/api/admin.js` | Approve handler (lines ~286-330) — FSA pre-fill fetches address/postcode/description from FSA API using `claim.fsa_id` |
| `schema.sql` | D1 schema — `claims.fsa_id` is already nullable, `listings.fsa_id` is nullable |
| `scripts/generate_restaurant_pages.py` | Static page generator — reads from `data/restaurants.json` (FSA-sourced), generates `/r/{city}/{slug}/` |
| `functions/r/_middleware.js` | `/r/` alias resolver — handles short-name URLs. Currently assumes all pages are FSA-backed static files. |

### Current flow (FSA-only)

```
User types name → /api/search (FSA API proxy, Thai-filtered)
     ↓
User selects from results → selectedRestaurant = {id, name, city, address, ...}
     ↓
User fills details → submitClaim() → POST /api/claim {..., fsa_id: selectedRestaurant.id}
     ↓
Admin views pending → Approve → FSA pre-fill (fetch address/postcode/description from FSA API using fsa_id)
     ↓
Listing created in D1 → magic link sent → owner edits
     ↓
Page served from static /r/{city}/{slug}/ (generated from restaurants.json)
```

### Where non-FSA vendors are blocked

1. **`claim/index.html` line 379**: `if (!selectedRestaurant.id)` — blocks submission if no FSA ID
2. **`claim/index.html` lines 312-318**: Search only queries `/api/search` which only queries FSA API
3. **`functions/api/search.js`**: Only searches FSA API — no non-FSA data source
4. **`functions/api/admin.js` lines 288-330**: Approve handler's FSA pre-fill block is gated on `if (claim.fsa_id)` — technically skips if null, but address/postcode/description end up empty
5. **`scripts/generate_restaurant_pages.py`**: Reads from `restaurants.json` (FSA-sourced only) — non-FSA listings would never get static pages

### What could break if changed carelessly

- **Claim form**: Adding a manual path must not break existing FSA autocomplete flow. The submit guard must distinguish FSA vs manual submissions.
- **Admin approve**: Must handle `fsa_id = null` without crashing. Current code already guards with `if (claim.fsa_id)`, so it won't crash — but the resulting listing has empty address/postcode/description, which will look broken on the live site.
- **Duplicate detection**: Currently checks by `restaurant_name + city`. Manual entries could collide with FSA entries. Need a `source` field to distinguish.
- **Page generation**: Non-FSA pages won't exist as static files. The `/r/` middleware would 404. Need a dynamic serving path.
- **Sitemap**: Non-FSA pages won't appear. Need to either include them in sitemap generation or accept they're discoverable only via internal links.
- **SEO/AEO**: Pages without FSA hygiene scores, rating dates, or structured scores need different schema (no `aggregateRating`, no `additionalProperty` hygiene scores).
- **Search/API**: `/api/search` only returns FSA results. Non-FSA listings won't appear in site search.

### Smallest safe place to patch

The claim form + claim API + admin approve are the minimum. Page serving can start with a simple D1-backed Cloudflare Pages Function, avoiding the complexity of touching the static generator.

---

## Proposed Approach

### Core design decisions

1. **Extend, don't replace** — Keep existing FSA claim flow untouched. Add a parallel "manual" path.
2. **Flag with `source` column** — Add `source TEXT DEFAULT 'fsa'` to claims table. Manual entries get `source = 'manual'`.
3. **Manual address collection** — When user toggles "My restaurant isn't in the FSA database", show name + address + postcode + city + type fields (no autocomplete).
4. **Admin handles differently** — Manual claims show a "Manual entry — no FSA data" badge. On approve, use the manually-entered address (no FSA pre-fill attempt). Require admin to verify address before approving.
5. **Dynamic page serving** — New Cloudflare Pages Function at `functions/r/manual/_middleware.js` or `functions/r/manual/[slug].js` that queries D1 and renders a page template. No static generation needed.
6. **Schema adaptation** — Non-FSA pages use `LocalBusiness` schema instead of `FoodEstablishment` (no FSA ratings to display). Omit hygiene score bars, rating circles, and FSA-specific structured data.

### What this does NOT do

- Does NOT modify the static page generator
- Does NOT add non-FSA listings to `restaurants.json` or `data/`
- Does NOT change FSA claim flow
- Does NOT add non-FSA listings to `/api/search`
- Does NOT add non-FSA listings to sitemap (Phase 2)
- Does NOT create `/r/{city}/{slug}/` paths for non-FSA (uses `/r/manual/{slug}/` instead)

---

## Phase 2 — Plan

### Task 1: Add `source` column to claims table

**Objective:** Distinguish FSA claims from manual claims in D1.

**Files:**
- Modify: `schema.sql:5-21` — add `source TEXT DEFAULT 'fsa'` to claims table
- Execute: D1 migration via Cloudflare Dashboard or `wrangler d1 execute`

**SQL:**
```sql
ALTER TABLE claims ADD COLUMN source TEXT DEFAULT 'fsa';
```

**Risk:** None. New column with default — existing rows get `'fsa'`, backward-compatible.

**Verification:** `SELECT id, restaurant_name, source FROM claims LIMIT 5;` — all existing should show `fsa`.

---

### Task 2: Add manual entry form to claim page

**Objective:** Let vendors submit without FSA autocomplete.

**File:** `claim/index.html`

**Changes:**
1. Add a "My restaurant isn't in the FSA database" link/button below the search box (around line 315)
2. On click, show manual entry fields: restaurant name, address line 1, address line 2, postcode, city (text), business type (dropdown: restaurant/takeaway/stall/market/pop-up/catering)
3. Set `selectedRestaurant = { id: null, name: <manual>, city: <manual>, address: <manual>, postcode: <manual>, source: 'manual', business_type: <manual> }`
4. Modify `submitClaim()` line 379: change guard from `if (!selectedRestaurant.id)` to `if (!selectedRestaurant.id && selectedRestaurant.source !== 'manual')`
5. Add `source: selectedRestaurant.source || 'fsa'` to the POST body
6. When `source === 'manual'`, send `address` and `postcode` from manual fields in the POST body

**Exact insertion point:** After the `searchResults.innerHTML` "No Thai restaurants found" message (line 316), add a manual entry trigger.

**Risk:** Must not break existing FSA flow. The toggle must clear/hide manual fields when user goes back to FSA search. Test both paths.

**Verification:** 
- FSA path: search "thai" → select result → fill form → submit (unchanged behavior)
- Manual path: click "not in FSA" → fill manual fields → submit (new behavior, `source: 'manual'`, `fsa_id: null`)

---

### Task 3: Update claim API to accept manual submissions

**Objective:** Accept `source: 'manual'` and manual address fields in `POST /api/claim`.

**File:** `functions/api/claim.js`

**Changes:**
1. Extract `source`, `address`, `postcode` from request body (line 25)
2. When `source === 'manual'`, require `address` and `postcode` in addition to `restaurant_name` and `city`
3. Insert `source` into the claims INSERT (line 84-86)
4. After successful insert, also INSERT a listing row with the manual address (so the listing exists immediately — admin just needs to approve the claim, the listing is pre-created with manual data)

Wait — let me reconsider. Currently listings are only created on admin approve. Creating them on claim submit is a bigger change. Let me keep it simpler: just pass the address through to the claim, and have the admin approve handler use it.

**Revised changes:**
1. Extract `source`, `address`, `postcode` from body
2. When `source === 'manual'`, require `address` and `postcode`
3. Store `source` in claims INSERT
4. No listing creation on submit — keep existing flow

**Risk:** The `address` and `postcode` fields don't exist on the claims table. Need to either add columns or pass them via `verification_notes` as JSON. Simplest: add `address TEXT` and `postcode TEXT` columns to claims.

**Verification:** POST with `source: 'manual'` → claim appears in admin with manual badge.

---

### Task 4: Add address/postcode columns to claims table

**Objective:** Store manually-entered address data on the claim record.

**SQL:**
```sql
ALTER TABLE claims ADD COLUMN address TEXT;
ALTER TABLE claims ADD COLUMN postcode TEXT;
```
(Or store as JSON in verification_notes — simpler, no schema change. Decision: JSON in verification_notes is hacky. Add proper columns.)

**File:** `schema.sql:5-21`

**Risk:** Minimal. New nullable columns, no existing data affected.

---

### Task 5: Update admin approve handler for manual claims

**Objective:** Handle `source = 'manual'` claims differently on approval.

**File:** `functions/api/admin.js` (around lines 286-330)

**Changes:**
1. When `claim.source === 'manual'` and `claim.fsa_id` is null: skip FSA pre-fill entirely
2. Use `claim.address` and `claim.postcode` for the listing's address/postcode (currently these come from FSA pre-fill)
3. Generate a simpler description without FSA rating references: `"{name} is a {type} in {city}, located at {address}."` 
4. Set `listing.fsa_id = null` explicitly

**Risk:** The current pre-fill code (lines 288-330) is already guarded by `if (claim.fsa_id)`. For manual claims with `fsa_id = null`, this block is skipped entirely — no crash. But the listing ends up with empty address/postcode. Need to use `claim.address` and `claim.postcode` instead.

**Verification:** Approve a manual claim → check D1: listing should have address, postcode, description (no FSA scores).

---

### Task 6: Create dynamic page serving for manual listings

**Objective:** Serve non-FSA listing pages at `/r/manual/{slug}/` from D1.

**File:** Create `functions/r/manual/[slug].js` (Cloudflare Pages dynamic route)

**Approach:**
1. Extract slug from URL path
2. Look up listing in D1 by slug (use a new `slug` column on listings, or compute from restaurant_name + city)
3. Render HTML using a minimal template (inline in the function, ~50 lines)
4. Template includes: restaurant name, type, address, description, city, claim CTA
5. No FSA-specific elements (no hygiene circle, no score bars, no FSA rating badge)
6. Schema: `LocalBusiness` (not `FoodEstablishment`) — no `aggregateRating`
7. Cache: 1 hour `Cache-Control` header
8. `noindex` initially — let pages earn indexing after quality review

**Template design:**
- Same green/cream color scheme as FSA pages
- Simplified single-column layout (no trust sidebar — no FSA data to show)
- H1: `{name} — {type} in {city}`
- Description paragraph
- Address block
- "Claim this listing" CTA (if not already claimed)
- Breadcrumb: ThaiData > Manual Listings > {name}

**Risk:** New function, no impact on existing routes. If the function fails, only manual listing pages are affected. The `/r/manual/` prefix keeps them namespaced away from FSA-backed `/r/{city}/{slug}/` routes.

**Verification:** Visit `/r/manual/test-listing/` → should render or 404 gracefully.

---

### Task 7: Add slug column to listings table

**Objective:** Enable URL-based lookup for manual listings.

**SQL:**
```sql
ALTER TABLE listings ADD COLUMN slug TEXT;
CREATE INDEX IF NOT EXISTS idx_listings_slug ON listings(slug);
```

On approve of a manual claim, compute slug from restaurant_name (using existing `slugify()` logic, ported to JS). Store on the listing row.

**Verification:** `SELECT id, restaurant_name, slug FROM listings WHERE fsa_id IS NULL;`

---

### Task 8: Add admin UI indicators for manual claims

**Objective:** Admin can distinguish manual claims at a glance.

**File:** `admin/index.html`

**Changes:**
1. In the pending/rejected/approved claim table rows, show a "Manual" badge when `claim.source === 'manual'`
2. In the detail modal, show "Source: Manual entry (not in FSA database)" when applicable
3. Show manually-entered address in the detail modal

**Risk:** Cosmetic only — no functional change.

---

### Task 9: Link manual listings from relevant pages

**Objective:** Make manual listings discoverable.

**Files:**
- `/r/` hub page — add a "Manual Listings" section or link
- Or create a simple `/manual-listings` index page listing all approved manual listings

**Approach:** Minimal — add a small card to the `/r/` hub: "Don't see your restaurant? It might be a manual listing. [View manual listings →](/r/manual/)" with a simple index.

This is the lowest priority task. Can be a separate PR.

---

## Risks, Tradeoffs, and Open Questions

### Risks

| # | Risk | Severity | Mitigation |
|---|------|:--------:|------------|
| 1 | Manual claims bypass FSA verification — could allow fake/spam listings | MEDIUM | Admin must manually verify each. Add note: "Manual entries require address verification." |
| 2 | Non-FSA pages have no FSA hygiene data — look "thin" compared to FSA pages | LOW | Acceptable tradeoff. These are supplementary listings, not replacements. |
| 3 | Slug collisions — two manual listings could compute the same slug | LOW | Append numeric suffix on collision (same pattern as existing generator line 364-367). |
| 4 | D1 query on every manual page load — performance/cost | LOW | 1-hour cache. Manual listings are low-traffic by nature. |
| 5 | `source` column requires D1 migration | LOW | Non-destructive ALTER TABLE. Existing rows get default 'fsa'. |
| 6 | Manual listing pages not in sitemap → slower indexing | LOW | Accept for Phase 1. Add to sitemap in Phase 2 if they gain traction. |
| 7 | Claim form gets longer → conversion drop for FSA claims | LOW | Manual toggle is hidden behind a small link, not a prominent button. |

### Tradeoffs

- **Dynamic vs static pages**: Dynamic (D1-backed) means no regeneration step, instant live on approve. Tradeoff: slower page load (D1 query) offset by 1h cache.
- **Separate namespace** (`/r/manual/` vs `/r/{city}/`): Cleaner separation, no collision with FSA pages. Tradeoff: less SEO-friendly URL structure. Acceptable — these are supplementary.
- **No FSA data integration**: Manual listings won't appear in city stats, MCP tools, or `/api/v1/cities.json`. Tradeoff: simpler code, no pipeline changes.

### Open questions for Jonathan

1. **Are market stalls/festival vendors the primary use case?** If yes, the address field needs to handle "Manchester Christmas Market" or "Magic of Thailand Festival" as locations — not just street addresses.

2. **Should manual listings appear on city pages?** Currently city page stats come from `restaurants.json` (FSA-only). Mixing manual entries would require pipeline changes. Recommendation: no, keep them separate for Phase 1.

3. **Should manual listings have `/r/{city}/{slug}/` URLs eventually?** They could, but that requires touching the alias resolver and sitemap. Recommendation: Phase 2, after manual listings prove useful.

4. **Business type options for manual entries**: restaurant, takeaway, stall, market, pop-up, catering, food truck, home-based — which ones? Recommendation: start with restaurant/takeaway/stall/market/pop-up.

---

## Implementation Order

```
Task 1: D1 migration — ADD source to claims          (2 min)
Task 4: D1 migration — ADD address, postcode to claims (2 min)
Task 7: D1 migration — ADD slug to listings            (2 min)
Task 2: Claim form UI — manual entry toggle + fields   (15 min)
Task 3: Claim API — accept manual submissions          (10 min)
Task 5: Admin approve — handle manual claims            (10 min)
Task 6: Dynamic page function — /r/manual/[slug]        (20 min)
Task 8: Admin UI indicators                              (5 min)
Task 9: Discovery links                                  (5 min)
```

**Total estimated time:** ~70 minutes. All tasks are independent of each other except Task 5 depends on Task 3, and Task 6 depends on Task 7.

---

## Verification Checklist (Phase 4)

After implementation:
- [ ] FSA claim flow: search → select → submit → approve → page live (unchanged)
- [ ] Manual claim flow: toggle → fill fields → submit → approve → page live at `/r/manual/{slug}/`
- [ ] Admin sees "Manual" badge on manual claims
- [ ] Manual claim approve uses manual address (check D1: address populated, fsa_id null)
- [ ] Manual listing page renders with name, type, address, description
- [ ] Manual listing page has no FSA-specific elements (hygiene circle, score bars)
- [ ] Manual listing page has LocalBusiness schema (not FoodEstablishment)
- [ ] `GET /api/claim?email=X` returns manual claims with `source: 'manual'`
- [ ] Existing tests pass: `cd /opt/thaidata-repo && python3 -m pytest tests/ -x -q`
