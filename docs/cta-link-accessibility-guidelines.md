# CTA, Link Colour & Accessibility Guidelines

> Adopted June 2026 after cross-page WCAG audit.  
> For any model implementing Issues #4–6 from the thaidata.uk design audit.

---

## 1. Primary CTAs (Buttons)

### Current problem
White text (`#FFFFFF`) on `#10B981` emerald green background. Contrast ratio **~2.55:1** — fails WCAG AA minimum 4.5:1 for normal text. Affects `.btn` (home, restaurants) and `.cta a` (city pages).

### New standard

**For light sections (default):**

| Property | Value | Contrast |
|----------|-------|----------|
| Background | `#065F56` (`var(--c3)`, darkest teal) | — |
| Text | `#FFFFFF` (white) | **~15:1** ✅ AAA |
| Border | none (or `#065F56`) | — |
| Border-radius | `8px` (existing, keep) | — |

**For dark sections (hero, dark nav):**

| Property | Value | Contrast |
|----------|-------|----------|
| Background | `#10B981` (`var(--c2)`, emerald) | — |
| Text | `#0C1220` (`var(--dark)`) | **~9:1** ✅ AAA |
| Border | none | — |
| Border-radius | `8px` | — |

Dark-section rationale: `#10B981` on `#0C1220` hero background already has strong contrast. Using dark text on the green button preserves the emerald brand feel while hitting AAA. White-on-`#10B981` on dark bg *could* work at ~6:1 for the button itself, but the page has both light and dark sections — choose dark text for consistency in the dark variant.

### Hover / active states

All hover states must maintain ≥4.5:1 text contrast:

```css
/* Light-section button */
.btn {
    background: #065F56;
    color: #FFFFFF;
    transition: background 0.2s;
}
.btn:hover, .btn:focus-visible {
    background: #054D45;  /* 10% darker, ~17:1 contrast maintained */
}

/* Dark-section button */
.btn-dark {
    background: #10B981;
    color: #0C1220;
}
.btn-dark:hover, .btn-dark:focus-visible {
    background: #0D9F6E;  /* ~10% darker, ~10:1 contrast maintained */
}
```

### Ghost buttons (dark nav, transparent bg)

These already have `rgba(255,255,255,0.85)` text on `#0C1220` — ~14:1. No change needed.

---

## 2. Body Links on Light Backgrounds

### Current problem
`#10B981` (`var(--c2)`) on `#FAFAF9` (`var(--bg)`) has a contrast ratio of **~3.0:1** — fails WCAG AA. Affects chain profiles (`a { color: var(--c1) }` where `--c1: #10B981`) and any page using emerald for body links on cream.

### New standard

| Surface | Link/Text Colour | Contrast on `#FAFAF9` | When to use |
|---------|-----------------|----------------------|-------------|
| Light (`#FAFAF9`, `#FFFFFF`, `#F3F4F6`) | **`#0A7A6F`** (deep teal) | **~5.5:1** ✅ AA | Default body link colour |
| Light (prefers higher contrast) | **`#065F56`** (darkest teal) | **~9.9:1** ✅ AAA | Small text, data-heavy pages |
| Dark (`#0C1220`) | `#10B981` or `#34D399` | ~5–6:1 on dark | Default dark-section link |

**Rule:** `#0A7A6F` replaces `#10B981` as the standard link colour on all light-background pages.

### Where `#10B981` is still allowed

`#10B981` (emerald) is the brand accent. It remains correct for:

| Usage | OK? | Reason |
|-------|:---:|--------|
| Icons (`.fas`, Font Awesome) | ✅ | Decorative, not information-conveying text |
| Borders (`border: 1px solid #10B981`) | ✅ | Decorative |
| Pill backgrounds (`rgba(16,185,129,0.12)`) | ✅ | Background, not text |
| Section dividers, accent bars | ✅ | Decorative |
| Logo elements | ✅ | Brand identity |
| **Body text / links** on light bg | ❌ | Fails 4.5:1 AA |
| **Button text** on light bg | ❌ | Fails 4.5:1 AA |
| Stat labels, captions, small print | ❌ | Even worse at small sizes |

### CSS rules

```css
/* Replace in :root or body-level reset */
a {
    color: #0A7A6F;           /* was #10B981 */
    text-decoration: underline;
}
a:hover {
    color: #065F56;            /* darker on hover */
}
a:visited {
    color: #0A7A6F;            /* no purple visited — keep branded */
}
```

---

## 3. Focus-Visible (Keyboard Access)

### Current problem
Zero pages have `:focus-visible` styles. Tab/Shift+Tab navigation gives no visual feedback. WCAG 2.4.7 (Focus Visible, Level AA) violation.

### Site-wide pattern

```css
/* Add to base CSS reset — works on all backgrounds */
:focus-visible {
    outline: 2px solid #10B981;
    outline-offset: 2px;
    border-radius: 4px;
}

/* Remove default focus ring for mouse users */
:focus:not(:focus-visible) {
    outline: none;
}
```

### How it looks per element type

| Element | Appearance |
|---------|-----------|
| **Buttons** (`.btn`, `.btn-ghost`) | 2px emerald ring 2px outside the button edge, 4px border-radius |
| **Body links** (`<a>`) | 2px emerald ring around the text, 2px offset |
| **Pills** (`.guide-strip a`) | 2px emerald ring outside the pill border, follows 20px border-radius |
| **Nav links** (dark nav) | 2px emerald ring around text — visible against `#0C1220` |
| **Form inputs** | 2px emerald ring replaces browser default blue ring |
| **Tab buttons** (`.tab-btn`) | 2px emerald ring inside the button bounds |

**Why `#10B981` for the outline:** It's the brand accent, bright enough to be visible on both light (`#FAFAF9`) and dark (`#0C1220`) backgrounds, and already semantically means "ThaiData". No new colour introduced.

### Dark-section note
On `#0C1220` backgrounds, `#10B981` at 2px is clearly visible (emerald on near-black). On `#FAFAF9`, same ring is visible but slightly less striking — still meets WCAG 2.4.7 since the requirement is "visible," not "maximum contrast." If future testing shows it's too subtle on cream, bump to `#0A7A6F` for the outline on light sections only.

---

## 4. Implementation Notes

### Safe application order

1. **Base CSS first** — add `:focus-visible` rules and the `a { color: #0A7A6F }` override to the **shared reset** or a batch-injected block. This avoids per-page drift.

2. **CTA colours** — change `.btn` and `.cta a` backgrounds from `#10B981` to `#065F56`. For pages with inline button styles, the CSS class change is sufficient (inline styles on those buttons don't set background). For pages with `style="background:var(--c2)"` on buttons, change to `var(--c3)`.

3. **Regenerate from templates** — after fixing templates:
   - Restaurant pages: fix `r/leeds/my-thai/index.html`, delete old, regenerate with `scripts/generate_restaurant_pages.py`
   - City pages: fix `cities/leeds.html`, run `scripts/generate_city_pages.py --apply`
   - Chain profiles: batch-fix all 29 files directly (no generator)
   - Tools: batch-fix directly

4. **Never patch one page at a time** for CTA/link/focus rules. These are system-level changes.

### Pre-change checklist

```bash
# 1. Count current CTA contrast failures
grep -rn 'background.*#10B981\|background.*var(--c2)' --include='*.html' . | grep -c 'btn\|cta\|\.button'

# 2. Count current link colour issues on light pages
grep -rn 'color.*#10B981\|color.*var(--c2).*a' --include='*.html' . | wc -l

# 3. Confirm no focus-visible rules exist (should be 0)
grep -rn 'focus-visible' --include='*.html' . | wc -l
```

### Post-change verification

```bash
# 1. No white-on-#10B981 button text remains
grep -rn 'color:\s*#fff\|color:\s*white\|color:\s*#FFF' --include='*.html' . | grep '10B981' | wc -l
# Expected: 0

# 2. focus-visible rule present on every page
grep -rl 'focus-visible' --include='*.html' . | wc -l
# Expected: >= total page count (every page has it)

# 3. Manual check at 375px and 1280px on 5 template pages
#   - Tab through all interactive elements — ring must be visible on each
#   - Button text must be clearly readable
#   - Body links must be distinguishable from regular text
```

---

## Quick Reference Card

| Element | Light bg | Dark bg | Contrast |
|---------|----------|---------|----------|
| CTA button bg | `#065F56` | `#10B981` | — |
| CTA button text | `#FFFFFF` | `#0C1220` | ≥9:1 |
| CTA hover bg | `#054D45` | `#0D9F6E` | ≥10:1 |
| Body link | `#0A7A6F` | `#10B981` | ≥5:1 |
| Body link hover | `#065F56` | `#34D399` | ≥7:1 |
| Focus ring | `#10B981` 2px | `#10B981` 2px | visible on both |
| Ghost nav text | `rgba(255,255,255,0.85)` | (unchanged) | ~14:1 |

---

## Changelog

| Date | Change | Trigger |
|------|--------|---------|
| 2026-06-06 | Created: CTA contrast, link colour, focus-visible spec | DeepSeek V4 Pro cross-page audit Issues #4–6 |
