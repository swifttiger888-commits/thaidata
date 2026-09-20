# Proposal: Separate "Listing Claimed" from "Owner Verified"

**Status:** Awaiting approval — nothing built.
**Date:** 2026-09-12
**Trigger:** Claim #26 (Tong Thai, Bradford) approved 33s after submission, `admin_notes`
empty, verification notes admit *"Ownership to be confirmed by owner when they complete
details via magic link."* Page renders **Owner Verified ✓** anyway.

---

## 1. Problem

One badge ("Owner Verified ✓") currently means two different things depending on which
claim you look at:

| Meaning | Reality today |
|---|---|
| We approved a claim from someone representing the business | 25 of 25 claims |
| We actually confirmed the person owns the business | Chao Phraya + Thai Aroy Dee (Johnny himself), disputed |

The badge is emitted by `/r/_middleware.js` based on a single condition:
`claims.claim_status = 'approved'`. There is no field that distinguishes an outreach
approval from a verified owner.

**Consequences:**
- Page tells Google and diners "Owner Verified" for restaurants whose own record says
  ownership is unconfirmed.
- Cannot retroactively separate the two populations — the distinction was never recorded.
- Any future claim approved the same way inherits the same false signal.

---

## 2. Proposed design

Two independent signals, recorded separately at claim level.

| Badge | Field value | Means | Trigger |
|---|---|---|---|
| **Listing Claimed** | `verification_level = 'claimed'` | We approved a claim from someone representing this business | Claim approved (existing flow) |
| **Owner Verified** | `verification_level = 'verified'` | We confirmed the claimer owns the business | Manual admin action, explicit evidence |

Default for all existing and future rows: `'claimed'`. Badge upgrades only by deliberate
admin action.

---

## 3. Open decisions (needed before build)

These are policy, not code. Recommend deciding all three before implementation starts.

### 3.1 What satisfies verification?

Pick one rule and write it down, or the field drifts:

- [ ] Companies House officer/director name matches claimer name
- [ ] FSA registration contact matches claimer email/phone
- [ ] Callback to the phone number already listed on the FSA record
- [ ] Email from the business domain (fails for Gmail-only independents)
- [ ] Manual judgement, noted in `admin_notes`

**Recommendation:** callback to the FSA-listed phone number, with the outcome recorded in
`admin_notes`. Cheap, evidenced, works for Gmail-only businesses.

### 3.2 Does verification gate editing?

Currently `injectClaimedEnrichment()` applies owner-supplied `description`, `phone`,
`website`, `opening_hours`, `features`, `price_range` and `photos` to the page for **any**
approved claim. At `claimed` level that means a non-verified claimant can rewrite public
content on the page.

| Option | Effect | Risk |
|---|---|---|
| **A.** Editing open at `claimed`, badge differs | Outreach prospects can self-serve immediately | Non-owner can edit public copy |
| **B.** Editing requires `verified` | Clean separation | Outreach conversion flow stalls — bad for the funnel |

**Recommendation:** Option A for now (badge is the signal, not the gate), but log every
owner edit with a timestamp so abuse is traceable. Revisit if a bad edit occurs.

### 3.3 Migration of existing 25 claims

- All existing rows → `'claimed'` (safe default, accurate).
- Claim #25 (Thai Aroy Dee) and #21 (Chao Phraya) — both have Johnny as claimer. Decide:
  bump to `'verified'` (you know the owner) or leave at `'claimed'` until evidenced.
- **Recommendation:** leave at `'claimed'`. If they get bumped without evidence the field
  becomes meaningless again.

---

## 4. Implementation (smallest PR)

### 4.1 Schema — 1 migration

```sql
ALTER TABLE claims ADD COLUMN verification_level TEXT NOT NULL DEFAULT 'claimed';
ALTER TABLE claims ADD COLUMN verified_at TEXT;
```

D1 has no migration runner in this repo — apply via `wrangler d1 execute`
(then mirror in a checked-in `.sql` file for reproducibility).

### 4.2 Admin API — `functions/api/admin.js`

- Extend the allowed action list (line ~242) with `'verify'`.
- Add a `verify` branch mirroring `reopen`:
  - Require `claim_status = 'approved'` (can't verify an unapproved claim)
  - `UPDATE claims SET verification_level = 'verified', verified_at = datetime('now'), admin_notes = ?`
  - Require non-empty `admin_notes` — this is the evidence record
  - Optional `unverify` action to reverse
- Return `verification_level` in the `onRequestGet` claims list (line ~168 `SELECT c.*`
  already covers it once the column exists).

### 4.3 Badge gating — `templates/restaurant.html` (SCOPED — see §9)

**Correction to earlier draft:** the badge is NOT server-rendered into static HTML by
the generator, and NOT emitted by `_middleware.js`. It is client-side JS in the template.

Verified facts:
- Badge markup: `templates/restaurant.html` line ~1146, `<div id="claimed-badge" style="display:none">`
- Present in all 1,264 generated pages (as inert markup — hidden by default)
- Unhidden by client-side JS at line ~1288
- **No full regeneration required** — template change + JS only

Current gate (line ~1288) is `hasOwnerData`:

```js
var hasOwnerData = listing.description || listing.phone || listing.opening_hours ||
    (listing.photos && listing.photos.length > 0) ||
    (listing.menu_highlights && listing.menu_highlights.length > 0) ||
    (listing.features && listing.features.length > 0) ||
    listing.social_instagram || listing.social_facebook;
```

**New finding — this is a bug independent of the badge question:** the badge is not gated
on claim status or verification at all. Any listing with any owner-populated field gets
"Owner Verified ✓" automatically. A `claimed`-level listing that fills in a phone number
is badged as owner-verified.

**Change:**
- Add `verification_level` to the `/api/listings` response.
- Gate on `listing.verification_level === 'verified'` for the "Owner Verified ✓" badge.
- Render "Listing Claimed" state otherwise (needs distinct markup, not just different words).

### 4.3b API surface — `functions/api/listing.js`

Must return `verification_level` alongside existing listing fields, or the template gate
has nothing to read.

### 4.4 Out of scope for this PR

- Existing issues #2–#4 from the Tong Thai review (hygiene copy conflict, Google
  attribution) — separate work.
- The `[The owner can edit this description…]` placeholder strip — **do this today,
  independently.** One-line removal in `admin.js` line ~346, plus regeneration of
  affected pages.

---

## 5. Tests required

| # | Test | Method |
|---|---|---|
| 1 | Default: new claim → `claimed`, no "Owner Verified" badge | Submit test claim, inspect page |
| 2 | `verify` action flips field + badge | PUT `verify` with notes, re-fetch page |
| 3 | `verify` rejected when claim not approved | PUT `verify` on a pending claim → 400 |
| 4 | `verify` rejected without `admin_notes` | PUT `verify` empty notes → 400 |
| 5 | Idempotency: double `verify` → no duplicate side effects | PUT `verify` twice |
| 6 | Existing 25 claims render "Listing Claimed" after migration | Spot-check 3 pages + count |
| 7 | JSON-LD unaffected by badge change | Diff JSON-LD before/after |
| 8 | Cache behaviour: badge change visible after cache expiry | Check `max-age=3600` (line ~242) — may need purge |

---

## 6. Risks

| Risk | Mitigation |
|---|---|
| Badge copy lives in generated static HTML, not middleware — larger change than expected | Scope the string location **first**; if it's in all ~1,265 generated pages, this becomes a full regeneration |
| Cache: middleware sets `max-age=3600`, so badge changes lag up to 1h | Accept, or purge on verify |
| Two similar badges confuse visitors | Copy must be visually distinct, not just different words |
| Field drifts if verification rule isn't written down | Make `admin_notes` mandatory on `verify` |

---

## 7. Sequencing

1. **Now (independent):** strip `[The owner can edit…]` placeholder from `admin.js`, regenerate.
2. **Decide:** §3.1 verification rule, §3.2 gating, §3.3 migration.
3. **Scope:** locate badge string origin in generator/templates.
4. **Build:** schema → admin API → middleware → tests.
5. **Verify:** all 8 tests, then spot-check 3 live pages.

---

## 8. Estimate

### Confirmed scope (2026-09-12) — badge JS is inlined, regeneration required

| Step | Effort |
|---|---|
| Extract badge logic → `/js/listing-badge.js` | ~30 min |
| Placeholder strip (`admin.js` line ~346) | ~15 min |
| Schema migration | ~15 min |
| Admin API `verify` / `unverify` actions | ~45 min |
| `/api/listing.js` returns `verification_level` | ~15 min |
| Badge gating + "Listing Claimed" markup | ~30 min |
| Full regeneration (1,264 pages) + diff review | ~30 min |
| Tests (8 from §5) | ~1h |
| **Total** | **~4h** |

**Critical path note:** the regeneration is unavoidable for this change because the badge
JS is inlined. Extracting to `/js/` first means it is the *last* regeneration needed for
badge work. Doing it the other way (edit inline) means the next badge tweak regenerates
all 1,264 pages again.

---

## 9. Scoping result (2026-09-12)

Completed before committing to an estimate. Corrections to the original draft:

| Assumption in draft | Reality |
|---|---|
| Badge is server-rendered static HTML | ❌ It's client-side JS in `templates/restaurant.html` |
| Badge is emitted by `_middleware.js` | ❌ Middleware does Quick Facts only |
| Badge is gated on `claim_status = 'approved'` | ❌ Gated on `hasOwnerData` — no claim/verification check at all |
| Full regeneration not needed | ❌ **Needed** — badge JS is inlined into all 1,264 pages |

**New bug found during scoping:** "Owner Verified ✓" currently shows for any listing where
the owner populated *any* field. It is not a verification signal at all today — it's an
"owner has edited something" signal wearing verification language. This strengthens the
case for the proposed split, and means the current badge is more misleading than #26 alone
suggested.

**Recommended first action:** extract the badge logic from the template into
`/js/listing-badge.js` before making any behaviour change. This makes future badge changes
free (no regeneration) and makes the current bug fixable in one place.

---

## 10. Questions for Johnny (blocking)

1. **§3.1** What satisfies verification? (recommend: callback to FSA-listed phone, noted in `admin_notes`)
2. **§3.2** Does verification gate editing, or is the badge the only signal? (recommend: badge only, log edits)
3. **§3.3** Bump Chao Phraya / Thai Aroy Dee to `verified`, or leave all 25 at `claimed`? (recommend: leave)
4. **§8** Extract to `/js/listing-badge.js` first, or edit inlined JS? (strongly recommend: extract)
5. **Sequencing** Placeholder strip alone first, or fold into this PR? (recommend: alone, today)

**No full regeneration required.** The badge is client-side JS in
`templates/restaurant.html`. ~~No full regeneration required.~~ **WRONG — see §8/§9.
The JS is inlined into all 1,264 pages, so a regeneration IS required.**

**CAVEAT CONFIRMED 2026-09-12 — the JS is INLINED. A regeneration IS required.**

Verified:
- `hasOwnerData` appears as raw source in generated pages (`r/bradford/tong-thai-restaurant/index.html` line 1205)
- Present in **1,264 of 1,264** generated pages
- No external badge JS file exists in the repo
- `templates/restaurant.html` line 1237 is an inline `<script>` block, not `<script src>`

So a template-only edit does **not** reach existing pages.

**Two options:**

| Approach | Effort | Trade-off |
|---|---|---|
| **A.** Edit inlined JS, regenerate all 1,264 pages | ~3h + regen | Big diff; every future badge tweak needs another full regen |
| **B.** Extract badge logic to `/js/listing-badge.js`, then edit | ~3.5h + **one** regen | Big diff once; badge changes are free forever after |

**Recommendation: B.** This repo has already had repeated badge/CTA iterations (see git log:
`Mock 3: contact strip`, `Show Google rating on claimed listing pages (variant B)`). Inlined
JS makes each iteration a 1,264-file diff. Extracting it now costs +30 min and removes that
cost permanently — and it also makes the current bug fixable in one place, which matters
because the bug affects every claimed listing, not just #26.

**Regeneration risk:** all 1,264 pages change, so the diff must be inspected for unintended
drift (whitespace, dates, FSA data refresh). Recommend regenerating on a branch, diffing,
and checking that only expected lines changed.

---

## 9. Scoping result (2026-09-12)

Completed before committing to an estimate. Key correction to the original draft:

| Assumption in draft | Reality |
|---|---|
| Badge is server-rendered static HTML | ❌ It's client-side JS in `templates/restaurant.html` |
| Badge is emitted by `_middleware.js` | ❌ Middleware does Quick Facts only |
| Badge is gated on `claim_status = 'approved'` | ❌ It's gated on `hasOwnerData` — no claim/verification check at all |
| Full regeneration needed | ❌ Not needed, **unless** template JS is inlined (see §8) |

**New bug found during scoping:** "Owner Verified ✓" currently shows for any listing where
the owner populated *any* field. It is not a verification signal at all today — it's an
"owner has edited something" signal wearing verification language. This strengthens the
case for the proposed split, and means the current badge is more misleading than #26 alone
suggested.

**Recommended first action:** extract the badge logic from the template into
`/js/listing-badge.js` before making any behaviour change. This makes future badge changes
free (no regeneration) and makes the current bug fixable in one place.
