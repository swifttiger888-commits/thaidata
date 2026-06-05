# City Page Policy — `/cities/[slug]`

> Defines how city pages behave across their full lifecycle. This document is the contract between the generator, editors, and validation pipeline. No generator logic shall be written or merged until this policy is agreed.

---

## 1. Modes and Meanings

Every city page operates in exactly one mode at any time. The mode determines what the generator may do to the file.

### 1.1 `programmatic`

| Property | Value |
|---|---|
| **Meaning** | Page is fully generated from templates and live data. The generator owns 100% of the HTML. |
| **Who may change it** | The generator (daily/weekly runs). Editors may override by setting `hybrid` or `manual`. |
| **Generator read access** | Full file read (to validate schema, check freshness). |
| **Generator write access** | Full file overwrite. The generator may rewrite the entire page body. |
| **Schema injection** | All schema blocks are injected by the generator. Schema is built from data, validated, then inserted. |
| **Validation** | Full validation: schema, markers, mode consistency, DOM thresholds. |

A programmatic page may still contain `<!-- AUTO:... -->` markers — they exist for forward compatibility when the page is later promoted to `hybrid` — but the generator does not rely on them during programmatic writes.

### 1.2 `hybrid`

| Property | Value |
|---|---|
| **Meaning** | Page has a mix of editorial content and auto-managed data blocks. The generator may only touch content inside marked `<!-- AUTO: -->` zones. |
| **Who may change it** | Editors (any content outside AUTO zones). Generator (content inside AUTO zones only). |
| **Generator read access** | Full file read (to locate AUTO blocks, validate schema). |
| **Generator write access** | **Only** the content between `<!-- AUTO:name -->` and `<!-- END:AUTO:name -->` markers. Nothing else in the file is modified. |
| **Schema injection** | Schema blocks inside `<!-- AUTO:schema -->` are regenerated. Any editorial schema outside AUTO zones is preserved untouched. |
| **Validation** | Full validation, plus marker integrity checks (every open must have a close). |

### 1.3 `manual`

| Property | Value |
|---|---|
| **Meaning** | Page is fully owned by editors. The generator must never read or write the file. |
| **Who may change it** | Editors only. |
| **Generator read access** | **None.** The generator skips manual pages entirely — no reads, no writes, no schema checks. |
| **Generator write access** | **None.** The generator never opens a manual page file. |
| **Schema injection** | Not touched by the generator. Schema on manual pages is the editor's responsibility. |
| **Validation** | Not performed by the generator pipeline. Manual pages are outside its scope. |

### 1.4 `quarantined`

| Property | Value |
|---|---|
| **Meaning** | Page is excluded from generation and publishing due to validation errors, marker corruption, or configuration conflicts. Requires explicit action to re-enable. |
| **Who may change it** | Generator (auto-imposes). Editors (explicitly resolve cause and set to active mode). |
| **Generator read access** | Read only — to validate whether quarantine condition is resolved. |
| **Generator write access** | **None.** Quarantined pages are never written by the generator. The previously deployed version remains live. |
| **Schema injection** | Not performed. |
| **Validation** | Quarantined pages are checked first — if the cause is resolved and `quarantined: false` is set, the page returns to normal processing on the next run. |

---

## 2. Source of Truth and Precedence

Three signals may attempt to define a page's mode. They must agree. When they disagree, a clear rule determines how the generator responds.

### 2.1 The three signals

| Signal | Location | Purpose |
|---|---|---|
| **Registry** | `.cities.json` → `cities[slug].mode` | Configuration intent. Human-editable. |
| **HTML safeguard** | `<!-- CITIES-MODE: manual -->` in the HTML file (first line) | Production override. Survives git operations, cherry-picks, merges. |
| **Manual marker** | `<!-- MANUAL -->` in the HTML file | Explicit editorial lockdown. Every `.html` file in the directory is scanned for this marker before any other processing. |

### 2.2 Precedence (highest to lowest)

```
1. HTML marker:   <!-- MANUAL -->         ← Overrides EVERYTHING
2. HTML comment:  <!-- CITIES-MODE: X --> ← Overrides registry
3. Registry:      .cities.json mode       ← Default, overridden by either above
```

### 2.3 Conflict handling

| Scenario | Generator action |
|---|---|
| HTML says `<!-- MANUAL -->` but registry says `programmatic` | **Quarantine.** The file and registry disagree. Something is out of sync. The generator quarantines the page and logs an error with both conflicting values. |
| HTML says `<!-- CITIES-MODE: manual -->` but registry says `hybrid` | **Quarantine.** Same logic — the HTML comment is authoritative, and registry must match. |
| HTML says `<!-- CITIES-MODE: hybrid -->` but no `<!-- AUTO -->` zones exist | **Quarantine.** Hybrid requires AUTO zones to function. Their absence indicates corruption or incomplete migration. |
| Registry entry missing for an existing `.html` file | **Treat as `programmatic` for this run, then write the correct entry.** The generator infers the mode from markers present and updates `.cities.json`. No quarantine. |
| HTML has no mode comment, registry has no entry (new city) | Treat as `programmatic` (see Section 7). |

### 2.4 CI treatment of conflicts

| Severity | CI action |
|---|---|
| Any quarantine-triggering conflict | **Hard fail.** CI blocks deployment until resolved. |
| Mode mismatch that doesn't trigger quarantine (e.g. missing registry entry) | **Soft warning.** CI passes. Generator self-heals on the next run. |

---

## 3. AUTO-Block Behavior and Failure Handling

AUTO zones are the mechanism by which the generator manages content on `hybrid` pages. Each zone is delimited by HTML comments.

### 3.1 Recognised AUTO zones

```
<!-- AUTO:schema --> ... <!-- END:AUTO:schema -->
<!-- AUTO:market-snapshot --> ... <!-- END:AUTO:market-snapshot -->
<!-- AUTO:top-rated --> ... <!-- END:AUTO:top-rated -->
<!-- AUTO:chain-presence --> ... <!-- END:AUTO:chain-presence -->
<!-- AUTO:postcode-areas --> ... <!-- END:AUTO:postcode-areas -->
<!-- AUTO:faq --> ... <!-- END:AUTO:faq -->
```

### 3.2 Locating and replacing

1. The generator scans the HTML for `<!-- AUTO:name -->`.
2. It finds the matching `<!-- END:AUTO:name -->`.
3. Everything between (inclusive) is replaced with fresh content for that zone.
4. Replacement preserves the exact marker delimiters so the next run can find them.

### 3.3 Failure cases

| Failure | Generator action | Log level |
|---|---|---|
| **Missing open marker** (`<!-- AUTO:X -->` expected but absent) | **Quarantine** the page. The zone it should manage cannot be located. | ❌ ERROR |
| **Missing close marker** (`<!-- END:AUTO:X -->` expected but absent) | **Quarantine** the page. An unclosed zone could lead to corrupted content if the generator attempts replacement. | ❌ ERROR |
| **Nested markers** (e.g. `AUTO:faq` inside `AUTO:schema`) | **Quarantine** the page. Nested AUTO zones create ambiguity and are never valid. | ❌ ERROR |
| **Duplicated markers** (two `<!-- AUTO:faq -->` with the same name) | **Quarantine** the page. The generator cannot determine which instance to replace. The ambiguity must be resolved by removing the duplicate. | ❌ ERROR |
| **Marker moved from expected position** (e.g. `AUTO:top-rated` was moved inside the footer) | **Update in place.** The marker's current position is respected. Log a **warning** with the old and new line numbers so editors can verify layout intent. | ⚠️ WARNING |
| **Marker content manually edited** (editor modified text inside AUTO zone) | **Overwrite on next run.** AUTO zones are managed content. If the editor wants to customise it, the zone should be moved outside the AUTO markers or the page should be promoted to `manual`. | ℹ️ INFO |

### 3.4 Rationale

- **Quarantine (not fail-build)** — one corrupted page should not bring down the entire 253-city generation. The generator reports the error, quarantines the one page, and continues with the rest. The previously deployed version of that page stays live.
- **Quarantine (not auto-recreate)** — if an editor removed a marker deliberately (e.g. restructuring the page layout), auto-recreating it could conflict with their design intent. Quarantine forces explicit resolution.

---

## 4. Mode Transitions and Their Effects

### 4.1 Allowed transitions

```
null → programmatic        ← New city discovered
programmatic → hybrid      ← Editor customisation
programmatic → manual      ← Full editorial takeover
hybrid → manual            ← Full editorial takeover
hybrid → programmatic      ← Rollback (rare)
manual → hybrid            ← Allowed but requires editor action (add AUTO markers)
manual → programmatic      ← Allowed but removes all editorial content

any → quarantined          ← Forced by the generator on validation/marker failure
quarantined → programmatic ← After resolution
quarantined → hybrid       ← After resolution
quarantined → manual       ← After resolution
```

### 4.2 Transition effects

| Transition | Existing AUTO content | Schema blocks | Editor actions required |
|---|---|---|---|
| `null → programmatic` | Not applicable | Generated fresh | None — auto-initialised |
| `programmatic → hybrid` | Preserved in place | Regenerated inside AUTO zones | Editor may add content outside AUTO zones |
| `programmatic → manual` | **Stripped** (removed from HTML) | **Removed** — editor writes their own | Verify page content; add own schema |
| `hybrid → manual` | **Stripped** (removed from HTML) | **Removed** — editor writes their own | Verify page content; add own schema |
| `hybrid → programmatic` | Stripped (no longer needed) | Regenerated | Removes editorial content — get approval first |
| `manual → hybrid` | Editor must insert AUTO markers manually | Generated inside AUTO zones | Add `<!-- AUTO:... -->` markers for each zone the generator should manage |
| `manual → programmatic` | Irrelevant — full overwrite | Regenerated | All editorial content is lost — get approval first |
| `any → quarantined` | Frozen (not written) | Frozen | Fix the trigger condition, unset `quarantined` |
| `quarantined → active` | Regenerated in new mode | Regenerated in new mode | Ensure markers valid, schema valid, mode consistent |

### 4.3 Deprecation behaviour (→ `manual`)

When a page transitions from `programmatic` or `hybrid` to `manual`:

1. **Default: strip.** The generator removes all `<!-- AUTO:... --> ... <!-- END:AUTO:... -->` blocks from the HTML. Content outside those blocks is preserved untouched.
2. **Opt-in freeze:** If `.cities.json` has `"on_deprecation": "freeze"` for that city, AUTO blocks are left in place but never refreshed. The page freezes with its last generated state.
3. An injection comment is added at the top of the HTML: `<!-- CITIES-MODE: manual — auto blocks removed on 2026-06-05 -->`
4. The transition is logged to `.cities.json` → `transitions` array.

**Rationale for `strip` as default:** a page going `manual` means an editor is taking responsibility for its content. They should not inherit auto-generated content that goes stale silently. The opt-in freeze exists for cases where the generated content is "good enough" baseline and the editor only wants to stop future overwrites.

---

## 5. Quarantine Rules

### 5.1 Triggers

A page is quarantined when any of the following occur:

| Trigger | Example |
|---|---|
| Schema validation failure | JSON-LD block fails to validate against its JSON Schema |
| Marker corruption | Missing open or close on an AUTO zone |
| Mode conflict | HTML says `<!-- MANUAL -->` but registry says `programmatic` |
| Required data missing | City has no restaurant data in `restaurants.json` |
| Duplicate or nested markers | Two `AUTO:faq` blocks in one file; `AUTO:faq` inside `AUTO:schema` |
| Unrecognised mode value | `.cities.json` says `mode: "invalid"` |

### 5.2 Behaviour

- The generator **does not write or publish** quarantined pages.
- The previously deployed version remains live and unchanged.
- Quarantine state is recorded in `.cities.json`:

```json
{
  "cities": {
    "manchester": {
      "mode": "hybrid",
      "quarantined": true,
      "quarantine_reason": "Missing <!-- END:AUTO:faq --> marker",
      "quarantine_date": "2026-06-05"
    }
  }
}
```

- The generator reports quarantines to stdout and exits with code 0 (doesn't fail the whole build — quarantined pages are expected to occur and should be handled gracefully).

### 5.3 Recovery

1. Editor resolves the root cause (fixes marker, repairs schema, reconciles mode).
2. Editor sets `"quarantined": false` in `.cities.json`.
3. Optionally removes `quarantine_reason` and `quarantine_date` fields.
4. Next generator run picks up the page normally.
5. If the page was previously `manual`, it returns to `manual` (the mode is preserved in `.cities.json`).
6. If the root cause is not resolved, the generator re-quarantines on the same run and logs an error.

**Required checks before unquarantine:**
- [ ] All AUTO markers present and correctly paired (for hybrid pages)
- [ ] Mode in `.cities.json` matches mode in HTML comment (if present)
- [ ] Schema blocks valid against their JSON Schema
- [ ] City has restaurant data available (minimum 1 restaurant)

---

## 6. Audit Trail / Transitions Log

Every mode change is recorded in `.cities.json` within the city's entry.

### 6.1 When a transition is logged

- A new entry is appended when:
  - The mode actually changes (`programmatic → hybrid`, `hybrid → manual`, etc.)
  - A page enters or exits quarantine (`any → quarantined`, `quarantined → previous`)
  - A new city page is initialised (`null → programmatic`)
- No entry is appended for routine regeneration runs where the mode stays the same.

### 6.2 Required fields

```json
"transitions": [
  {
    "from": "programmatic",
    "to": "hybrid",
    "date": "2026-06-05",
    "reason": "Added editorial intro covering Northern Quarter scene"
  }
]
```

| Field | Required | Notes |
|---|---|---|
| `from` | Yes | Previous mode value, or `null` for initial creation |
| `to` | Yes | New mode value |
| `date` | Yes | ISO 8601 date (`2026-06-05`) |
| `reason` | Yes | Free-text explanation of why the transition occurred |

### 6.3 Review usage

- The transitions array should be reviewed during PRs that modify city page modes.
- A transition from `hybrid → programmatic` without a documented reason should be flagged — it destroys editorial content.
- A rapid series of transitions back and forth (e.g. `programmatic → hybrid → programmatic → hybrid` within 7 days) may indicate process confusion and warrants discussion.

---

## 7. Schema Policy (Content–Schema Contract)

### 7.1 Hard rules

1. **Every schema block must be:**
   - Valid JSON (parses without error).
   - Valid against its JSON Schema (`.schema.json` in `schemas/`).
   - Matching on-page content. No fact appears in schema that is not also visible in the HTML. Google requires this and it is enforced by the validator.

2. **Allowed schema types on city pages:**

| Schema type | Condition |
|---|---|
| `BreadcrumbList` | Always allowed. Maps nav path. |
| `City` | Allowed when Wikidata entry exists. Must include `sameAs`. |
| `ItemList` (of `Restaurant`) | Allowed for top-rated lists. Each entry must match a visible restaurant name and rating on the page. |
| `FAQPage` | Allowed for programmatic FAQ blocks. Each Q&A must be visible on the page. |
| `Restaurant` (individual) | Allowed only inside `ItemList`. Each restaurant must link to its `/r/` page. |

3. **Forbidden schema types:**
   - `AggregateRating` — see Section 7.2.
   - Any schema type not reviewed and documented in this table.

### 7.2 `AggregateRating` prohibition

**FSA hygiene scores are NOT aggregate ratings.** They are single-point official inspection scores. Using `AggregateRating` would misrepresent the data source to Google and risk rich-result penalties.

**Alternative:** Use `additionalProperty` to surface FSA scores:

```json
{
  "@type": "Restaurant",
  "name": "Hong Thai",
  "additionalProperty": {
    "@type": "PropertyValue",
    "name": "FSA Hygiene Rating",
    "value": "5"
  }
}
```

This is semantically honest, does not trigger Google's aggregate review rules, and communicates the same information.

### 7.3 New schema type approval

No new schema type may be deployed without:

1. **Semantic fit documented** — a brief rationale for why this type fits our content. Filed in `schemas/SCHEMA_DECISIONS.md`.
2. **JSON Schema created** — in `schemas/<type>.schema.json`.
3. **Unit tests written** — covering valid and invalid inputs for the builder.
4. **Content–schema match verified** — every field in the schema must map to visible on-page content.
5. **Schema builder module created** — in `scripts/schema/<type>.py`, returning validated dicts.

### 7.4 Content–schema matching rule

The validator enforces that every user-meaningful schema fact must have a visible on-page equivalent. No percentage-based pass rule is used — pass/fail is determined by explicit field mapping.

**User-meaningful fields** (must have visible on-page equivalent):
- Restaurant `name` — must appear in the HTML body text
- `aggregateRating.ratingValue` (where used) — must appear in the HTML body
- `address.addressLocality` — must match the city heading or page title
- FAQ `Question.name` — must appear as visible text (heading or paragraph)
- FAQ `Answer.text` — must appear as visible text (paragraph or list)

**Exempt fields** (no on-page match required):
- `@context` — always `"https://schema.org"`, purely technical
- `@type` — machine type identifier
- `@id`, `itemid`, `url` — canonical URL identifiers
- `position` (ListItem) — internal ordinal, implicit in layout
- `sameAs` — Wikidata reference link, not user-visible content

If the validator finds a user-meaningful schema field whose value does not appear in the stripped HTML body, the page is quarantined with an error listing the mismatched fields.

**Implementation:** The HTML is stripped of all tags, comments, and script/style blocks. The remaining text is searched (case-insensitive, substring) for each user-meaningful schema value. This catches exact and near-exact matches (punctuation differences, whitespace). No fuzziness or threshold — every required value must be found.

---

## 8. Validation and CI Behaviour

### 8.1 Checks that must pass for a "green" page

| Check | Applies to | Failure result |
|---|---|---|
| Schema valid JSON | All pages with schema | Quarantine |
| Schema valid against `.schema.json` | All pages with schema | Quarantine |
| Content–schema match (≥90%) | All pages with schema | Quarantine |
| Marker integrity (all open/close paired) | Hybrid pages | Quarantine |
| Mode consistency (HTML vs registry) | All pages | Quarantine on conflict |
| City has ≥1 restaurant in data | All pages | Quarantine |
| Page size < 150KB | All pages | Warning (not quarantine) |
| Estimated DOM nodes < 1,500 | All pages | Warning (not quarantine) |
| No duplicate restaurant IDs in ItemList | Pages with ItemList | Quarantine |

### 8.2 Single-page failure vs build failure

- **A single page failure quarantines that page and the generator continues.** The previously deployed version stays live.
- The generator exits with code 0 (success) even when quarantines occur, because quarantines are an expected operational state.
- CI reports quarantined pages in its output as a summary table.
- CI **hard fails** only if the generator itself crashes or `.cities.json` becomes unparseable.

### 8.3 Build manifest

After each run, the generator writes a manifest to `cities/.build-manifest.json`:

```json
{
  "run_date": "2026-06-05",
  "total_cities": 253,
  "generated": {
    "programmatic": 230,
    "hybrid": 18,
    "manual": 1
  },
  "quarantined": [
    {
      "slug": "manchester",
      "reason": "Missing <!-- END:AUTO:faq --> marker"
    }
  ],
  "schema_blocks_validated": 422,
  "schema_blocks_failed": 0,
  "duration_seconds": 12.4
}
```

This manifest is human-readable CI output and can be consumed by the health check if desired.

---

## 9. Newly Discovered Cities

### 9.1 Trigger

A new city is "discovered" when a restaurant in `restaurants.json` has a `city` value that does not map to any existing slug in `.cities.json` or HTML file in `cities/`.

### 9.2 Auto-initialisation

On discovery, the generator:

1. Creates a new entry in `.cities.json`:
   ```json
   {
     "cities": {
       "new-city": {
         "tier": "standard",
         "mode": "programmatic",
         "quarantined": false,
         "transitions": [
           {"from": null, "to": "programmatic", "date": "2026-06-05", "reason": "Auto-created — new city with data in restaurants.json"}
         ]
       }
     }
   }
   ```
2. The new page is auto-created in `programmatic` mode using the standard template.
3. Tier is determined by restaurant count:
   - ≥ 13 restaurants → `enriched`
   - < 13 restaurants → `standard`
4. The new page is generated on the same run as discovery. No manual intervention needed.

### 9.3 Override

An editor may later modify `.cities.json` to change the mode or tier. The generator will respect the new value on the next run (subject to the precedence rules in Section 2).

---

## Revision History

| Date | Change |
|---|---|
| 2026-06-05 | Initial policy document |
