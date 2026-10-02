#!/usr/bin/env python3
"""
ThaiData UK — full menu page generator.

Turns a verified menu JSON (see menu_schema note below) into a static HTML page
that slots in beside the existing /r/<city>/<slug>/ listing page.

Design tokens are lifted verbatim from templates/restaurant.html so the menu page
matches the (well-built) restaurant template rather than the homepage stylesheet.

Usage:
    python3 scripts/build_menu_page.py menu.json r/leeds/thai-aroy-dee/menu/index.html

Input JSON schema:
{
  "restaurant": str, "city": str, "fsa_id": str, "address": str,
  "source": str,            # URL the menu was taken from
  "source_label": str,      # human label, e.g. "the restaurant's own PDF menu"
  "checked": "YYYY-MM-DD",  # date the menu was read
  "protein_tiers": [[proteins, price], ...],   # optional section-level pricing
  "categories": { "<name>": [ {num,name,description,price,vegetarian,heat}, ... ] },
  "addons": [ {num,name,description,price,vegetarian,heat}, ... ]
}
"""
import json, os, re, sys, html, datetime
from urllib.parse import quote

def money(p):
    """Normalise OCR spacing only. Never changes the value."""
    if not p:
        return None
    p = re.sub(r"£\s+", "£", str(p)).strip()
    # "£9.95/£10.95" -> "£9.95 / £10.95"
    p = re.sub(r"/(?=£)", " / ", p)
    return p


# --- guide-recipe linking (Oct 2026) ---
_ALIAS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "recipe_aliases.json")
_FILLER = {"the", "a", "an", "with", "without", "and", "or", "of", "style", "fresh"}


def _tokens(s):
    s = s.lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^\w\s]", " ", s)
    return [x for x in s.split() if x not in _FILLER]


def _load_aliases():
    try:
        return json.load(open(_ALIAS_PATH, encoding="utf-8"))
    except Exception:
        return {}


_ALIASES = _load_aliases()
_ALIAS_TOK = {
    s: [_tokens(a) for a in e.get("aliases", []) if _tokens(a)]
    for s, e in _ALIASES.items()
}


def recipe_slug_for(dish_name):
    """Return the recipe slug this menu line maps to, or None. Guide links only:
    the recipe page explains how the dish is typically made, never what this
    specific restaurant does."""
    if not dish_name:
        return None
    t = _tokens(dish_name)
    tset = set(t)
    joined = " ".join(t)
    for slug, e in _ALIASES.items():
        for th in e.get("thai", []):
            if th and th in dish_name:
                return slug
    best = None
    for slug, als in _ALIAS_TOK.items():
        for a in als:
            if len(a) >= 4:
                hit = all(x in tset for x in a)
            elif len(a) > 1:
                hit = " ".join(a) in joined
            else:
                hit = a[0] in tset
            if hit and (best is None or len(a) > best[1]):
                best = (slug, len(a))
    return best[0] if best else None


def recipe_title_for(slug):
    t = _ALIASES.get(slug, {}).get("title", "")
    t = re.sub(r"\s*\([^)]*\)\s*", " ", t)
    t = t.split("—")[0].split("–")[0].strip()
    return t or slug.replace("-", " ").title()

def esc(s):
    return html.escape(s or "", quote=True)

def dish_html(it, protein_tiers=None):
    price = money(it.get("price"))
    veg = it.get("vegetarian")
    spice = it.get("spice")
    celery = it.get("celery")
    num = it.get("num")
    # Keep the menu's own dish number visible so customers can cross-reference the
    # printed menu ("I'll have number 47"). Number + name live in one span so the
    # flex gaps in .dish-name don't separate them from each other.
    label = (f'<span class="dish-num">{num}.</span> {esc(it["name"])}'
             if num else esc(it["name"]))
    bits = [f'<li class="dish">']
    bits.append('<div class="dish-main">')
    bits.append('<div class="dish-head">')
    bits.append(f'<h3 class="dish-name"><span class="dish-label">{label}</span>')
    if veg:
        bits.append('<span class="badge badge-veg" title="Vegetarian">V</span>')
    if spice:
        bits.append(f'<span class="badge badge-spice" title="Spice level {spice}/5">🌶 {spice}</span>')
    if celery:
        bits.append('<span class="badge badge-celery" title="Contains celery">C</span>')
    bits.append("</h3>")
    if price:
        bits.append(f'<span class="dish-price">{esc(price)}</span>')
    bits.append("</div>")
    if it.get("description"):
        bits.append(f'<p class="dish-desc">{esc(it["description"])}</p>')
    if it.get("price_note"):
        bits.append(f'<p class="dish-note">{esc(it["price_note"])}</p>')
    rslug = recipe_slug_for(it.get("name") or "")
    if rslug:
        bits.append(
            f'<a class="recipe-link" href="/recipes/{rslug}/">'
            f'<img src="/recipes/{rslug}/{rslug}.jpg" alt="" loading="lazy" width="1200" height="675">'
            f'<span class="rl-text">Guide recipe — <strong>{esc(recipe_title_for(rslug))}</strong>'
            f' · how this dish is typically made</span></a>'
        )
    bits.append("</div></li>")
    return "".join(bits)

def build(data, dst=None):
    rname = data["restaurant"]
    city = data["city"]
    # The canonical URL and the breadcrumb link to the listing page must point at
    # where the file ACTUALLY lives. Deriving the slug from the restaurant name
    # diverges from the live listing pages as soon as a name contains punctuation:
    # "Ploy's Thai Bistro" slugifies to "ploy-s-thai-bistro" here, while its real
    # listing page is /r/kingston-upon-thames/ploys-thai-bistro/. The canonical then
    # pointed at a URL that does not exist, and the sitemap generator - which only
    # accepts a page whose canonical matches its own path - dropped the page
    # entirely, costing it all its search value. So prefer the output path, which is
    # authoritative, and fall back to the name only when it is not in the usual shape.
    slug_city = slug_name = None
    if dst:
        parts = os.path.normpath(os.path.abspath(dst)).split(os.sep)
        if len(parts) >= 4 and parts[-2] == "menu":
            slug_name, slug_city = parts[-3], parts[-4]
    if not slug_city or not slug_name:
        slug_city = re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-")
        slug_name = re.sub(r"[^a-z0-9]+", "-", rname.lower()).strip("-")
    listing_url = f"/r/{slug_city}/{slug_name}/"
    checked = data.get("checked") or datetime.date.today().isoformat()
    try:
        checked_human = datetime.date.fromisoformat(checked).strftime("%d %B %Y").lstrip("0")
    except ValueError:
        checked_human = checked

    cats = data["categories"]
    CATEGORY_ORDER = ["Starters", "Vegetarian Starters", "Soups", "Main Courses",
                      "Chef's Specials", "Fish Dishes", "Sizzling Dishes", "Salads",
                      "Noodle & Rice Dishes", "Side Dishes", "Hot Pots"]
    cats = {k: v for k, v in sorted(
        cats.items(),
        key=lambda kv: CATEGORY_ORDER.index(kv[0]) if kv[0] in CATEGORY_ORDER else 99,
    )}
    total = sum(len(v) for v in cats.values()) + len(data.get("addons") or [])
    priced = sum(1 for v in cats.values() for i in v if i.get("price"))

    # ---- section nav ----
    nav = "".join(
        f'<a class="navchip" href="#cat-{re.sub(r"[^a-z0-9]+","-",c.lower()).strip("-")}">{esc(c)}</a>'
        for c in cats
    )

    # ---- protein tier callout (Main Courses pricing) ----
    tiers = data.get("protein_tiers") or []
    tier_html = ""
    if tiers:
        rows = "".join(
            f'<li><span class="tier-proteins">{esc(t[0])}</span>'
            f'<span class="tier-price">{esc(money(t[1]))}</span></li>' for t in tiers
        )
        tier_html = f'<div class="tiers"><p class="tiers-label">Choose your protein</p><ul>{rows}</ul></div>'

    # ---- pricing policy callout (set-price menus, lunch deals, buffets) ----
    # Some menus price the whole meal rather than each dish ("any starter and main
    # course for 14.50"). Those dishes legitimately have no individual price, so
    # without surfacing the policy the page reads as a pricelist with no prices -
    # which looks broken and would rightly annoy the restaurant.
    pricing = data.get("pricing_notes") or []
    notes_html = ""
    if pricing:
        nrows = "".join(f"<li>{esc(n)}</li>" for n in pricing)
        notes_html = (f'<div class="pricing-notes"><p class="pricing-notes-label">'
                      f'How this menu is priced</p><ul>{nrows}</ul></div>')

    # ---- sections ----
    def dish_sort_key(x):
        """Dish numbers are printed strings ("8", "12a") but unnumbered dishes get
        an int fallback. Sorting the mixed types raised TypeError, which broke every
        menu that mixes numbered and unnumbered dishes. Numbered first, in numeric
        order; unnumbered keep their original order at the end."""
        n = x.get("num")
        try:
            return (0, int(str(n).strip()), "")
        except (TypeError, ValueError):
            return (1, 0, str(x.get("name", "")))

    sections = []
    for c, dishes in cats.items():
        cid = re.sub(r"[^a-z0-9]+", "-", c.lower()).strip("-")
        rows = "".join(dish_html(d) for d in sorted(dishes, key=dish_sort_key))
        callout = tier_html if c == "Main Courses" and tier_html else ""
        sections.append(
            f'<section class="cat" id="cat-{cid}">'
            f'<h2 class="cat-title">{esc(c)}</h2>{callout}'
            f'<ul class="dishes">{rows}</ul></section>'
        )
    if data.get("addons"):
        rows = "".join(dish_html(d) for d in data["addons"])
        sections.append(
            '<section class="cat" id="cat-addons"><h2 class="cat-title">Add to any meal</h2>'
            f'<ul class="dishes">{rows}</ul></section>'
        )

    # ---- schema.org Menu ----
    def mi(it):
        o = {"@type": "MenuItem", "name": it["name"]}
        if it.get("description"):
            o["description"] = it["description"]
        if money(it.get("price")):
            o["offers"] = {"@type": "Offer", "price": re.sub(r"[^0-9.]", "", money(it["price"]).split(" / ")[0]),
                           "priceCurrency": "GBP"}
        if it.get("vegetarian"):
            o["suitableForDiet"] = "https://schema.org/VegetarianDiet"
        return o

    menu_schema = {
        "@context": "https://schema.org",
        "@type": "Menu",
        "name": f"{rname} Menu",
        "inLanguage": "en-GB",
        "dateModified": checked,
        "hasMenuSection": [
            {"@type": "MenuSection", "name": c,
             "hasMenuItem": [mi(d) for d in sorted(v, key=dish_sort_key)]}
            for c, v in cats.items()
        ] + ([{"@type": "MenuSection", "name": "Add to any meal",
               "hasMenuItem": [mi(d) for d in data["addons"]]}] if data.get("addons") else []),
    }
    rest_schema = {
        "@context": "https://schema.org", "@type": "Restaurant", "name": rname,
        "address": {"@type": "PostalAddress", "streetAddress": data.get("address", ""),
                    "addressLocality": city, "addressCountry": "GB"},
        "servesCuisine": "Thai", "hasMenu": menu_schema,
    }

    return f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<!-- Set by scripts/build_menu_page.py. The /r/ middleware uses this marker to
     distinguish a genuine nested sub-page from the SPA fallback (which returns
     the homepage with HTTP 200 for any unmatched path). Do not remove. -->
<meta name="thaidata-page" content="menu">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(rname)} Menu — Full Prices &amp; Dishes | ThaiData UK</title>
<meta name="description" content="The full {esc(rname)} menu in {esc(city)} — {total} dishes with current prices, taken from the restaurant's own menu. First published online by ThaiData UK.">
<link rel="canonical" href="https://thaidata.uk/r/{slug_city}/{slug_name}/menu/">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700;800&amp;family=Inter:wght@400;500;600;700&amp;display=swap">
<script type="application/ld+json">{json.dumps(menu_schema, ensure_ascii=False, separators=(",",":"))}</script>
<script type="application/ld+json">{json.dumps(rest_schema, ensure_ascii=False, separators=(",",":"))}</script>
<style>
:root {{
            --ivory: #FBF7F0;
            --paper: #FFFFFF;
            --white: #FFFFFF;
            --cream: #FBF7F0;
            --ink: #1A1614;
            --ink-soft: #4A403C;
            --ink-mute: #7A6F6A;
            --hairline: #E7DFD5;
            --border: #E7DFD5;
            --border-light: #F2EDE6;
            --brand: #A3132B;
            --brand-press: #7E0E20;
            --brand-tint: #F7E8EB;
            --turmeric: #F2B21A;
            --jade: #047857;

            /* SEMANTIC - meaning, not brand. --success renders the FSA hygiene scale:
               5/5 is good, so it must stay green even though the brand is red. */
            --success: #047857;
            --success-dark: #065F46;
            --success-light: #D1FAE5;
            --amber: #B45309;
            --amber-light: #FEF3C7;
            --danger: #B91C1C;
            --danger-light: #FEE2E2;

            /* legacy aliases - the old tokens were named after their COLOUR, not their
               role, so the ~30 var() uses resolve with no rule edits */
            --green: var(--brand);
            --green-dark: var(--brand-press);
            --green-light: var(--brand-tint);
            --red: var(--danger);
            --red-light: var(--danger-light);
            --ink-secondary: var(--ink-soft);
            --ink-tertiary: var(--ink-mute);
--radius-sm:8px;
            --radius:12px;
            --radius-lg:16px;
            --shadow-sm:0 1px 2px rgba(0,0,0,.05);
            --shadow:0 1px 3px rgba(0,0,0,.1);
            --shadow-md:0 4px 6px -1px rgba(0,0,0,.1);
            --step--1:.875rem;
            --step-0:1rem;
            --step-1:1.25rem;
            --step-2:1.5rem;
            --step-3:2rem;
        }}
*{{box-sizing:border-box}}
body{{margin:0;background:#FAFAF9;color:var(--ink);font:16px/1.6 Inter,system-ui,sans-serif;-webkit-font-smoothing:antialiased}}
a{{color:var(--green-dark)}}
.wrap{{max-width:880px;margin:0 auto;padding:0 20px}}
header.masthead{{background:var(--white);border-bottom:1px solid var(--border);padding:20px 0}}
.crumb{{font-size:var(--step--1);color:var(--ink-secondary);margin:0 0 6px}}
.crumb a{{text-decoration:none}}
h1{{font-family:'Archivo', 'Inter', system-ui, sans-serif;font-weight: 800;font-size:var(--step-3);line-height:1.15;margin:0 0 8px}}
h1 em{{font-style: normal;color:var(--green-dark)}}
.meta{{font-size:var(--step--1);color:var(--ink-secondary);margin:0;display:flex;flex-wrap:wrap;gap:6px 14px}}
.meta b{{color:var(--ink);font-weight:600}}
.fsapill{{display:inline-block;background:var(--green-light);color:var(--green-dark);font-weight:700;font-size:.8125rem;padding:2px 9px;border-radius:999px}}
.notice{{background:var(--cream);border:1px solid #FDE68A;border-radius:var(--radius);padding:14px 16px;margin:22px 0;font-size:var(--step--1);color:#78350F}}
.notice a{{color:#78350F;font-weight:600}}
nav.catnav{{position:sticky;top:0;z-index:20;background:rgba(250,250,249,.95);backdrop-filter:blur(8px);border-bottom:1px solid var(--border);padding:11px 0;margin-bottom:8px}}
/* Right-edge fade signals that the chip strip scrolls horizontally.
   Without it the last chip is clipped flush at the viewport edge. */
nav.catnav::after{{content:"";position:absolute;top:0;right:0;bottom:0;width:38px;pointer-events:none;background:linear-gradient(to right,rgba(250,250,249,0) 0%,rgba(250,250,249,.96) 70%)}}
.navrow{{display:flex;align-items:center;gap:14px;max-width:880px;margin:0 auto;padding:0 20px}}
.navbrand{{flex:0 0 auto;font-weight:600;font-size:var(--step--1);color:var(--ink);white-space:nowrap;text-decoration:none;display:none}}
.navbrand:hover{{color:var(--green-dark)}}
@media (min-width:620px){{ .navbrand{{display:block}} }}
.chips{{display:flex;gap:8px;overflow-x:auto;padding:0;scrollbar-width:none;flex:1 1 auto;min-width:0}}
.chips::-webkit-scrollbar{{display:none}}
.navchip{{flex:0 0 auto;font-size:var(--step--1);font-weight:500;color:var(--ink-secondary);text-decoration:none;padding:5px 12px;border:1px solid var(--border);border-radius:999px;background:var(--white);white-space:nowrap}}
.navchip:hover{{border-color:var(--green);color:var(--green-dark)}}
section.cat{{padding:26px 0 6px;scroll-margin-top:calc(var(--navh, 78px) + 14px)}}
.cat-title{{font-size:var(--step-2);margin:0 0 14px;padding-bottom:9px;border-bottom:2px solid var(--green-light)}}
.tiers{{background:var(--green-light);border-radius:var(--radius);padding:14px 16px;margin:0 0 16px}}
.tiers-label{{margin:0 0 8px;font-size:.8125rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--green-dark)}}
.tiers ul{{list-style:none;margin:0;padding:0}}
.tiers li{{display:flex;justify-content:space-between;gap:16px;padding:3px 0;font-size:var(--step--1)}}
.tier-price{{font-weight:700;color:var(--green-dark)}}
ul.dishes{{list-style:none;margin:0;padding:0}}
.dish{{padding:13px 0;border-bottom:1px solid var(--border-light)}}
.dish:last-child{{border-bottom:0}}
.dish-head{{display:flex;justify-content:space-between;align-items:baseline;gap:14px}}
.dish-name{{font-size:var(--step-0);font-weight:600;margin:0;display:flex;align-items:center;gap:7px}}
.dish-label{{display:inline}}
.dish-num{{color:var(--ink-tertiary);font-weight:600;font-variant-numeric:tabular-nums}}
.badge{{font-size:.6875rem;font-weight:700;padding:1px 6px;border-radius:var(--radius-sm);line-height:1.5}}
.badge-veg{{background:var(--green-light);color:var(--green-dark)}}
.badge-spice{{background:#FEE2E2;color:#B91C1C}}
.badge-celery{{background:var(--border-light);color:var(--ink-tertiary)}}
.legend{{font-size:.8125rem;color:var(--ink-tertiary);margin:0 0 16px}}
.legend .badge{{vertical-align:middle;margin:0 3px}}
.dish-price{{font-weight:700;color:var(--green-dark);white-space:nowrap;font-variant-numeric:tabular-nums}}
.dish-desc{{margin:3px 0 0;font-size:var(--step--1);color:var(--ink-secondary);max-width:64ch}}
.dish-note{{margin:4px 0 0;font-size:.8125rem;color:var(--ink-tertiary);font-weight:500}}
.pricing-notes{{background:var(--green-light);border:1px solid rgba(16,185,129,.28);border-radius:var(--radius);padding:14px 18px;margin:0 0 22px}}
.pricing-notes-label{{font-size:.75rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-secondary);margin:0 0 7px}}
.pricing-notes ul{{list-style:none;margin:0;padding:0}}
.pricing-notes li{{font-size:.9375rem;line-height:1.5;color:var(--ink);padding:2px 0}}
.cta{{background:var(--white);border:1px solid var(--border);border-radius:var(--radius-lg);box-shadow:var(--shadow-sm);padding:24px;margin:34px 0 50px}}
.cta h2{{font-family:'Archivo', 'Inter', system-ui, sans-serif;font-weight: 800;font-size:var(--step-2);margin:0 0 8px}}
.cta p{{margin:0 0 16px;color:var(--ink-secondary);font-size:var(--step--1)}}
.btn{{display:inline-block;background:var(--green-dark);color:#fff;text-decoration:none;font-weight:600;padding:11px 22px;border-radius:999px;font-size:var(--step--1)}}
.recipe-link{{display:flex;align-items:center;gap:10px;margin:8px 0 0;padding:7px 9px;border:1px solid var(--border);border-radius:10px;text-decoration:none;background:#fff}}
.recipe-link img{{width:56px;height:38px;object-fit:cover;border-radius:6px;flex:0 0 auto}}
.recipe-link .rl-text{{font-size:.8125rem;color:var(--ink-secondary);line-height:1.4}}
.recipe-link strong{{color:var(--green-dark)}}
footer{{border-top:1px solid var(--border);padding:22px 0 40px;font-size:.8125rem;color:var(--ink-tertiary)}}
footer p{{margin:0 0 6px}}
@media (max-width:640px){{
  h1{{font-size:var(--step-2)}}
  .notice{{padding:11px 13px;margin:14px 0;font-size:.8125rem;line-height:1.5}}
  section.cat{{padding:20px 0 4px}}
  .cat-title{{font-size:var(--step-1)}}
  .dish{{padding:11px 0}}
}}
@media (min-width:900px){{
  /* 12 categories do not fit one strip in 880px, so the strip scrolled and cut a
     chip mid-word. Wrap on wide screens instead — every category is then visible
     without interaction. Mobile keeps the scroll strip, where wrapping to three
     rows would eat too much vertical space. */
  .chips{{flex-wrap:wrap;overflow-x:visible;gap:7px}}
  nav.catnav::after{{display:none}}
  .navchip{{padding:4px 11px;font-size:.8125rem}}
  .navrow{{gap:16px}}
}}
@media print{{
  nav.catnav,.cta{{display:none}}
  body{{background:#fff}}
  .dish{{break-inside:avoid}}
}}
em {{ font-style: normal; font-weight: 700; }}
</style>
</head>
<body>
<header class="masthead"><div class="wrap">
  <p class="crumb"><a href="/">ThaiData</a> › <a href="/r/{slug_city}/">{esc(city)}</a> › <a href="{listing_url}">{esc(rname)}</a></p>
  <h1>{esc(rname)} — <em>Full Menu</em></h1>
  <p class="meta">
    <span>{esc(data.get("address",""))}</span>
    <span><b>{total}</b> dishes</span>
    <span><b>{priced}</b> priced individually</span>
    {'<span class="fsapill">FSA 5/5</span>' if data.get("fsa_rating") else ''}
  </p>
</div></header>

<nav class="catnav"><div class="navrow"><a class="navbrand" href="{listing_url}">{esc(rname)}</a><div class="chips">{nav}</div></div></nav>

<main class="wrap">
  <div class="notice">
    Published by ThaiData UK from <a href="{esc(data.get('source','#'))}" rel="nofollow noopener" target="_blank">{esc(data.get('source_label','the restaurant&rsquo;s own menu'))}</a>, read {checked_human}.
    Prices are set by the restaurant — please confirm when ordering.
  </div>

  <p class="legend">Symbols: <span class="badge badge-spice">🌶 4</span> spice level (1&ndash;5) &nbsp;&middot;&nbsp; <span class="badge badge-celery">C</span> celery &nbsp;&middot;&nbsp; <span class="badge badge-veg">V</span> vegetarian</p>

  {notes_html}
  {"".join(sections)}

  <div class="cta">
    <h2>Own {esc(rname)}?</h2>
    <p>We've published your full menu to give it a page that's actually readable on a phone and findable on Google — free. Claim your listing to correct any price, edit descriptions, or add dishes.</p>
    <a class="btn" href="/claim/?restaurant={quote(rname)}&amp;city={quote(city)}">Claim this listing — free</a>
  </div>
</main>

<footer><div class="wrap">
  <p>Source: <a href="{esc(data.get('source','#'))}" rel="nofollow noopener" target="_blank">{esc(data.get('source_label','restaurant menu'))}</a> · read {checked}</p>
  <p>Guide recipes show how a dish is typically made — not this restaurant's own recipe. Thai names have no single English spelling, so the same dish may appear under different spellings here and elsewhere. Treat ingredients as a guideline, not a guarantee.</p>
  <p>ThaiData UK · <a href="{listing_url}">Restaurant details &amp; food hygiene rating</a> · <a href="/">All UK Thai restaurants</a></p>
</div></footer>
<script>
// The category nav is sticky and its height changes with how many rows the chips
// wrap to (one row on narrow screens, two or three on wider ones). A hardcoded
// scroll-margin-top therefore clips the target heading at some viewport widths.
// Publish the measured height as --navh so section anchors always clear it.
(function () {{
  var nav = document.querySelector('.catnav');
  if (!nav) return;
  function setNavHeight() {{
    document.documentElement.style.setProperty('--navh', nav.offsetHeight + 'px');
  }}
  setNavHeight();
  window.addEventListener('resize', setNavHeight);
  if (window.ResizeObserver) new ResizeObserver(setNavHeight).observe(nav);
  window.addEventListener('load', setNavHeight);
}})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    data = json.load(open(src, encoding="utf-8"))
    out = build(data, dst)
    open(dst, "w", encoding="utf-8").write(out)
    print(f"wrote {dst} ({len(out)} bytes)")
