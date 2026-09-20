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
import json, re, sys, html, datetime
from urllib.parse import quote

def money(p):
    """Normalise OCR spacing only. Never changes the value."""
    if not p:
        return None
    p = re.sub(r"£\s+", "£", str(p)).strip()
    # "£9.95/£10.95" -> "£9.95 / £10.95"
    p = re.sub(r"/(?=£)", " / ", p)
    return p

def esc(s):
    return html.escape(s or "", quote=True)

def dish_html(it, protein_tiers=None):
    price = money(it.get("price"))
    veg = it.get("vegetarian")
    heat = it.get("heat")
    bits = [f'<li class="dish">']
    bits.append('<div class="dish-main">')
    bits.append('<div class="dish-head">')
    bits.append(f'<h3 class="dish-name">{esc(it["name"])}')
    if veg:
        bits.append('<span class="badge badge-veg" title="Vegetarian">V</span>')
    bits.append("</h3>")
    if price:
        bits.append(f'<span class="dish-price">{esc(price)}</span>')
    bits.append("</div>")
    if it.get("description"):
        bits.append(f'<p class="dish-desc">{esc(it["description"])}</p>')
    if it.get("price_note"):
        bits.append(f'<p class="dish-note">{esc(it["price_note"])}</p>')
    bits.append("</div></li>")
    return "".join(bits)

def build(data):
    rname = data["restaurant"]
    city = data["city"]
    slug_city = re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-")
    slug_name = re.sub(r"[^a-z0-9]+", "-", rname.lower()).strip("-")
    listing_url = f"/r/{slug_city}/{slug_name}/"
    checked = data.get("checked") or datetime.date.today().isoformat()
    try:
        checked_human = datetime.date.fromisoformat(checked).strftime("%d %B %Y").lstrip("0")
    except ValueError:
        checked_human = checked

    cats = data["categories"]
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

    # ---- sections ----
    sections = []
    for c, dishes in cats.items():
        cid = re.sub(r"[^a-z0-9]+", "-", c.lower()).strip("-")
        rows = "".join(dish_html(d) for d in sorted(dishes, key=lambda x: x.get("num") or 0))
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
             "hasMenuItem": [mi(d) for d in sorted(v, key=lambda x: x.get("num") or 0)]}
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
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&amp;family=Instrument+Serif:ital@0;1&amp;display=swap">
<script type="application/ld+json">{json.dumps(menu_schema, ensure_ascii=False, separators=(",",":"))}</script>
<script type="application/ld+json">{json.dumps(rest_schema, ensure_ascii=False, separators=(",",":"))}</script>
<style>
:root{{
  --green:#10B981; --green-dark:#0A7A6F; --green-light:#D1FAE5;
  --ink:#1F2937; --ink-secondary:#6B7280; --ink-tertiary:#9CA3AF;
  --border:#E5E7EB; --border-light:#F3F4F6; --white:#FFF; --cream:#FFFBEB;
  --amber:#B45309; --amber-light:#FEF3C7;
  --radius-sm:8px; --radius:12px; --radius-lg:16px;
  --shadow-sm:0 1px 2px rgba(0,0,0,.05); --shadow:0 1px 3px rgba(0,0,0,.1);
  --shadow-md:0 4px 6px -1px rgba(0,0,0,.1);
  --step--1:.875rem; --step-0:1rem; --step-1:1.25rem; --step-2:1.5rem; --step-3:2rem;
}}
*{{box-sizing:border-box}}
body{{margin:0;background:#FAFAF9;color:var(--ink);font:16px/1.6 Inter,system-ui,sans-serif;-webkit-font-smoothing:antialiased}}
a{{color:var(--green-dark)}}
.wrap{{max-width:880px;margin:0 auto;padding:0 20px}}
header.masthead{{background:var(--white);border-bottom:1px solid var(--border);padding:20px 0}}
.crumb{{font-size:var(--step--1);color:var(--ink-secondary);margin:0 0 6px}}
.crumb a{{text-decoration:none}}
h1{{font-family:'Instrument Serif',Georgia,serif;font-weight:400;font-size:var(--step-3);line-height:1.15;margin:0 0 8px}}
h1 em{{font-style:italic;color:var(--green-dark)}}
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
section.cat{{padding:26px 0 6px;scroll-margin-top:78px}}
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
.badge{{font-size:.6875rem;font-weight:700;padding:1px 6px;border-radius:var(--radius-sm);line-height:1.5}}
.badge-veg{{background:var(--green-light);color:var(--green-dark)}}
.dish-price{{font-weight:700;color:var(--green-dark);white-space:nowrap;font-variant-numeric:tabular-nums}}
.dish-desc{{margin:3px 0 0;font-size:var(--step--1);color:var(--ink-secondary);max-width:64ch}}
.dish-note{{margin:4px 0 0;font-size:.8125rem;color:var(--ink-tertiary);font-weight:500}}
.cta{{background:var(--white);border:1px solid var(--border);border-radius:var(--radius-lg);box-shadow:var(--shadow-sm);padding:24px;margin:34px 0 50px}}
.cta h2{{font-family:'Instrument Serif',Georgia,serif;font-weight:400;font-size:var(--step-2);margin:0 0 8px}}
.cta p{{margin:0 0 16px;color:var(--ink-secondary);font-size:var(--step--1)}}
.btn{{display:inline-block;background:var(--green-dark);color:#fff;text-decoration:none;font-weight:600;padding:11px 22px;border-radius:999px;font-size:var(--step--1)}}
footer{{border-top:1px solid var(--border);padding:22px 0 40px;font-size:.8125rem;color:var(--ink-tertiary)}}
footer p{{margin:0 0 6px}}
@media (max-width:640px){{
  h1{{font-size:var(--step-2)}}
  .notice{{padding:11px 13px;margin:14px 0;font-size:.8125rem;line-height:1.5}}
  section.cat{{padding:20px 0 4px;scroll-margin-top:66px}}
  .cat-title{{font-size:var(--step-1)}}
  .dish{{padding:11px 0}}
}}
@media print{{
  nav.catnav,.cta{{display:none}}
  body{{background:#fff}}
  .dish{{break-inside:avoid}}
}}
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

  {"".join(sections)}

  <div class="cta">
    <h2>Own {esc(rname)}?</h2>
    <p>We've published your full menu to give it a page that's actually readable on a phone and findable on Google — free. Claim your listing to correct any price, edit descriptions, or add dishes.</p>
    <a class="btn" href="/claim/?restaurant={quote(rname)}&amp;city={quote(city)}">Claim this listing — free</a>
  </div>
</main>

<footer><div class="wrap">
  <p>Source: <a href="{esc(data.get('source','#'))}" rel="nofollow noopener" target="_blank">{esc(data.get('source_label','restaurant menu'))}</a> · read {checked}</p>
  <p>ThaiData UK · <a href="{listing_url}">Restaurant details &amp; food hygiene rating</a> · <a href="/">All UK Thai restaurants</a></p>
</div></footer>
</body>
</html>
"""

if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    data = json.load(open(src, encoding="utf-8"))
    out = build(data)
    open(dst, "w", encoding="utf-8").write(out)
    print(f"wrote {dst} ({len(out)} bytes)")
