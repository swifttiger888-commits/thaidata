# ThaiData Mobile Layout & Contrast Guidelines

> Adopted June 2026 after senior mobile audit.  
> For any front-end model (Claude, GPT, Flash) working on thaidata.uk pages.

---

## 1. Horizontal Overflow Prevention (MANDATORY)

### The Triple Lock

Every page MUST have all three of these. Missing any one = page slides sideways on mobile.

```css
/* LOCK 1 — html level (CSS overflow propagation demands this) */
html {
    overflow-x: hidden;
}

/* LOCK 2 — body level */
body {
    overflow-x: hidden;
}

/* LOCK 3 — media reset (prevents image/embedded overflow) */
img, svg, video, canvas {
    max-width: 100%;
    height: auto;
}
```

### Why `body` alone fails

CSS overflow on `<body>` propagates to the viewport (`<html>`) per spec. `body { overflow-x: hidden }` without `html { overflow-x: hidden }` does **not** lock the page — one-finger drag still slides it sideways. Both rules are required. This was the #1 complaint from the June 2026 audit and has recurred because models add only the `body` rule.

### Common overflow culprits (check these first)

| Pattern | Risk | Fix |
|---------|------|-----|
| Inline `width` in pixels > viewport | High | Use `max-width: 100%` or `clamp()` |
| `100vw` without accounting for scrollbar | Medium | Prefer `100%` inside a constrained parent |
| `overflow-x: auto` on a child inside an unconstrained parent | Medium | Ensure parent has `overflow-x: hidden` or constrained width |
| Tables wider than viewport | Medium | Wrap in `<div class="data-table-wrap" style="overflow-x:auto">` |
| `white-space: nowrap` on elements wider than viewport | Low | Use `flex-wrap: wrap` instead of `nowrap` where possible |
| Negative margins (`margin-left: -X`) | Low | Don't use; use padding + box-sizing instead |
| Fixed-position elements without `left:0; right:0` | Low | Always constrain to viewport edges |

### Quick audit command

```bash
# On any page, grep for the triple lock
grep -c 'overflow-x:\s*hidden' page.html
# Expect >= 2 (html + body)
grep -c 'max-width:\s*100%' page.html
# Expect >= 3 (img, svg, video)
```

---

## 2. Mobile Pill / Button Group Layout

### Pattern: Full-width stacked rows (≤600px)

For any horizontal button/pill strip (FREE GUIDES, tool selectors, filter rows), mobile layout follows this pattern:

```
Desktop (>600px):     [Pill A]  [Pill B]  [Pill C]  [Pill D]
Mobile (≤600px):      [████████ PILL A ████████]
                      [████████ PILL B ████████]
                      [████████ PILL C ████████]
                      [████████ PILL D ████████]
```

**All pills equal width, all full container width. Never tapered/uneven.**

### CSS template

```css
/* Desktop — horizontal wrap */
.pill-strip {
    display: flex;
    gap: 14px;
    padding: 18px 20px;
    align-items: center;
    flex-wrap: wrap;
    justify-content: center;
}

/* Mobile — stacked full-width */
@media (max-width: 600px) {
    .pill-strip {
        flex-direction: column;
        align-items: stretch;          /* ← critical, but often overridden by inline styles */
    }

    .pill-strip a,
    .pill-strip button {
        display: block;
        width: 100%;
        box-sizing: border-box;
        text-align: center;
    }
}
```

### The inline-style trap

If any element in your pill group has an inline `style="align-items:center"` or `style="justify-content:..."`, that inline style **wins over** the mobile `align-items: stretch` in your `@media` block. Inline styles always beat class-based CSS regardless of specificity.

**Two solutions (pick one):**

1. **CSS-only (preferred for surgical fixes):** Use `!important` in the media query to force full-width:
   ```css
   .pill-strip a { width: 100% !important; display: block !important; }
   ```

2. **Inline→class refactor (preferred for clean builds):** Move all layout styles out of inline `style=""` attributes into CSS classes, so media queries can override them normally. No `!important` needed.

### Pill CSS (branded)

```css
/* Pill base */
.pill-strip a {
    padding: 8px 16px;
    font-size: 0.85rem;
    text-decoration: none;
    background: rgba(16, 185, 129, 0.12);
    border: 1px solid rgba(16, 185, 129, 0.25);
    border-radius: 20px;
    transition: all 0.2s;
}

/* Section wrapper */
.pill-strip-wrapper {
    border-bottom: 1px solid var(--line);
    border-top: 1px solid var(--line);
    background: rgba(16, 185, 129, 0.05);
}
```

### Do NOT use these on mobile pill groups

- ~~`overflow-x: auto` + `white-space: nowrap`~~ — creates competing touch scroll zone
- ~~`flex-wrap: nowrap`~~ — pills overflow viewport
- ~~`inline-flex` without `flex-wrap: wrap`~~ — same problem

---

## 3. Contrast & Readability Requirements

### Colour palette (ThaiData design system)

```
--c1:  #0A7A6F    deep teal (primary)
--c2:  #10B981    emerald green (accent)
--c3:  #065F56    darkest teal (hover states, high-contrast text)
--dark: #0C1220   hero/nav background
--ink:  #0F172A   main body text
--ink2: #334155   secondary text
--ink3: #64748B   tertiary/muted
--ink4: #94A3B8   placeholder/low-emphasis
--bg:   #FAFAF9   page background
--bg2:  #F3F4F6   section alt background
--line: #E5E7EB   borders/dividers
```

### Foreground-on-background rules

| Element | Background | Foreground (text) | Foreground (icon) | Font size (mobile) |
|---------|-----------|-------------------|-------------------|--------------------|
| **Primary CTA** (`.btn`, dark hero) | `#10B981` | `#FFFFFF` | `#FFFFFF` | 0.9–1.0rem |
| **Primary CTA** (light sections) | `#0A7A6F` or `#10B981` | `#FFFFFF` | `#FFFFFF` | 0.9–1.0rem |
| **Ghost button** (dark nav) | transparent | `rgba(255,255,255,0.85)` | `#10B981` | 0.85rem |
| **Pill button** (`.guide-strip a`) | `rgba(16,185,129,0.12)` | **`#065F56`** | **`#065F56`** | 0.85rem |
| **Pill label** (`.guide-strip span`) | `rgba(16,185,129,0.05)` | `#10B981` | `#10B981` | 0.8rem |
| **Tab button** (`.tab-btn`) | `#FFFFFF` / `#F3F4F6` | `#0F172A` | — | 0.7rem |
| **Stat label** (`.insight-card-label`) | `#FFFFFF` | `#64748B` | — | 0.72rem |
| **Stat value** (`.insight-finding`) | `#FFFFFF` | `#0F172A` | — | 0.95rem |
| **Intel card title** | `#FFFFFF` | `#0F172A` | — | 1.4rem+ |
| **Intel card desc** | `#FFFFFF` | `#334155` | — | 0.95rem |
| **Intel link** | `#FFFFFF` | `#0A7A6F` | `#0A7A6F` | 0.95rem |

### The white-on-green failure pattern

**NEVER use `color:#fff` (or any white) on `rgba(16,185,129,0.12)` or lighter green backgrounds.** The rendered colour at 12% opacity over `#FAFAF9` is approximately `rgb(222, 242, 235)` — near-white. White text on a near-white background is invisible.

**Rule:** Any text on a green-tinted light background must use `#065F56` (darkest teal) or `#0F172A` (body ink). The pill border at `rgba(16,185,129,0.25)` is sufficient to convey "green brand" — the text doesn't need to be green too.

### Minimum contrast ratios (WCAG AA)

- Body text (`.ink`, `.ink2`): **4.5:1 minimum** against `#FAFAF9`
- Large text (headings, ≥18px bold): **3:1 minimum**
- UI components (icons, borders): visual distinction must be clear at arm's length on a phone
- Hover/focus states: must have visible change (background shift, underline, or border change)

---

## 4. Quick Checks for Layout Changes

### Before committing any CSS/HTML layout change

Run these checks at **375px** and **414px** viewport widths (cover iPhone SE through iPhone 15 Pro Max):

```bash
# 1. Verify triple-lock present
grep -c 'overflow-x:\s*hidden' page.html        # expect >= 2
grep -c 'max-width:\s*100%' page.html            # expect >= 3

# 2. No inline white-on-green failures
grep -n 'color:#fff.*rgba(16,185,129' page.html  # expect 0

# 3. No inline align-items that would override mobile stretch
grep -n 'align-items:\s*center' page.html        # audit each — move to class if needed

# 4. Verify viewport meta (complete single-line tag)
grep -n 'name=.viewport.' page.html              # must be full tag, not truncated

# 5. No nowrap horizontal strips
grep -n 'white-space:\s*nowrap.*flex' page.html  # expect 0
```

### Manual visual checks (DevTools mobile mode)

1. **Set viewport to 375×812** (iPhone SE). Drag sideways with one finger — page must not move horizontally.
2. **Scroll to pill/button groups** — all pills should be identical width, centered text, readable at arm's length.
3. **Check every section** for elements poking out of the viewport (images, tables, code blocks).
4. **Tap all buttons** — tap targets must be ≥44px tall (Apple HIG minimum).
5. **Set viewport to 414×896** (iPhone 11/XR). Repeat. Layout should be identical, just wider.

### Regression test

After any CSS change to shared rules (e.g. `.wrap`, reset, nav), spot-check **3 page types** at 375px:
- Home page (`index.html`)
- One city page (`cities/leeds.html`)
- One restaurant page (any `r/*/index.html`)

---

## Changelog

| Date | Change | Trigger |
|------|--------|---------|
| 2026-06-06 | Created: overflow triple-lock, pill layout pattern, contrast tables, quick-check script | DeepSeek V4 Pro mobile audit (overflow + FREE GUIDES contrast + reverse-pyramid) |
