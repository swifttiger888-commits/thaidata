#!/usr/bin/env python3
"""Generate the restaurant directory hub at /r/index.html.

The /r/ page is the main restaurant discovery hub, linking into city guides,
chain pages, and individual restaurant pages.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
import site_icons  # noqa: E402  (same-dir module, replaces Font Awesome)

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

OUTPUT = REPO / "r" / "index.html"

with open(REPO / "data" / "restaurants.json") as f:
    data = json.load(f)

restaurants = data["restaurants"]

# Load exclusions (moderation layer)
excluded_ids: set[int] = set()
excl_path = REPO / "data" / "exclusions.json"
if excl_path.exists():
    with open(excl_path) as f:
        excl_data = json.load(f)
    excluded_ids.update(excl_data.get("excluded_fsa_ids", []))

# Filter out excluded restaurants before any grouping/counting
active_restaurants = [r for r in restaurants if r["id"] not in excluded_ids]
# Pubs with Thai kitchens live in their own section (/pubs/) — keep them out of all counts
pubs = [r for r in active_restaurants if r.get("type") == "pub"]
active_restaurants = [r for r in active_restaurants if r.get("type") != "pub"]
total = len(active_restaurants)

# Group by city
by_city: dict[str, list[dict[str, Any]]] = defaultdict(list)
for r in active_restaurants:
    by_city[r["city"]].append(r)

def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s)
    return s.strip("-")

def rest_url(r: dict[str, Any]) -> str:
    return f"/r/{slugify(r['city'])}/{slugify(r['name'])}/"

# Stats
all_ratings = [int(r["hygiene_rating"]) for r in active_restaurants if r.get("hygiene_rating", "").isdigit()]
avg_overall = round(sum(all_ratings) / len(all_ratings), 1) if all_ratings else 0
five_star = sum(1 for r in all_ratings if r == 5)
five_pct = round(five_star / total * 100, 1)
dine_in_total = sum(1 for r in active_restaurants if r["type"] == "restaurant")
takeaway_total = total - dine_in_total
pubs_total = len(pubs)
cities_count = len(by_city)

# Top 10 by city
city_counts = [(city, len(rests)) for city, rests in by_city.items()]
city_counts.sort(key=lambda x: -x[1])
top_cities = city_counts[:10]

# Top-rated overall (must have 5/5)
top_rated = sorted(
    [r for r in active_restaurants if r.get("hygiene_rating") == "5"],
    key=lambda r: (r["name"].lower(), r["city"]),
)[:20]

# Chains
CHAIN_KEYWORDS: list[str] = [
    "giggling squid", "rosa thai", "busaba", "thaikhun", "camile",
    "thai square", "patara", "thai express", "mango tree", "sabai",
    "chaophraya", "sukhothai", "bangkok",
]
chain_restaurants: dict[str, list[dict[str, Any]]] = defaultdict(list)
for r in active_restaurants:
    name_lower = r["name"].lower()
    for chain in CHAIN_KEYWORDS:
        if chain in name_lower:
            chain_restaurants[chain].append(r)
            break

# London neighbourhood breakdown (from London guide data)
LONDON_NEIGHBOURHOODS: list[dict[str, Any]] = [
    {"id": "shoreditch", "name": "Shoreditch & Spitalfields", "postcodes": ["E1", "E2", "EC2A"]},
    {"id": "camden", "name": "Camden & Kentish Town", "postcodes": ["NW1", "NW3", "NW5"]},
    {"id": "kensington", "name": "Kensington & Chelsea", "postcodes": ["SW5", "SW7", "W8", "SW3"]},
    {"id": "hammersmith", "name": "Hammersmith & Shepherds Bush", "postcodes": ["W6", "W12", "W14"]},
    {"id": "soho", "name": "Soho & Chinatown", "postcodes": ["W1D", "WC2H", "W1F"]},
    {"id": "islington", "name": "Islington & Angel", "postcodes": ["N1", "N5"]},
    {"id": "notting-hill", "name": "Notting Hill & Bayswater", "postcodes": ["W11", "W10", "W2"]},
    {"id": "greenwich", "name": "Greenwich", "postcodes": ["SE10", "SE3"]},
    {"id": "putney", "name": "Putney & Wimbledon", "postcodes": ["SW15", "SW19"]},
    {"id": "battersea", "name": "Battersea & Clapham", "postcodes": ["SW11", "SW4", "SW8"]},
]
london_restaurants = [r for r in active_restaurants if r["city"] == "London"]

def outward(pc: str) -> str:
    if not pc:
        return ""
    parts = pc.split()
    return parts[0] if parts else pc.strip()

london_hood_counts = []
for hood in LONDON_NEIGHBOURHOODS:
    code_set = set(hood["postcodes"])
    count = sum(1 for r in london_restaurants if outward(r.get("postcode", "")) in code_set)
    london_hood_counts.append((hood, count))

london_hood_counts.sort(key=lambda x: -x[1])

# ── HTML ──────────────────────────────────────────────────────────────────────

STAR_ENTITY = "&#9733;"

# Top city cards
top_city_cards = ""
for city, count in top_cities:
    slug = slugify(city)
    top_city_cards += (
        f'<a href="/cities/{slug}" class="browse-card">'
        f'<span class="bc-name">{city}</span>'
        f'<span class="bc-count">{count}</span>'
        f'</a>'
    )

# Top rated restaurant links
top_rated_html = ""
for r in top_rated[:12]:
    url = rest_url(r)
    rtype = "Restaurant" if r.get("type") == "restaurant" else "Takeaway"
    top_rated_html += (
        f'<a href="{url}" class="rest-link">'
        f'<span class="rl-name">{r["name"]}</span>'
        f'<span class="rl-city">{r["city"]}</span>'
        f'<span class="rl-type">{rtype}</span>'
        f'</a>'
    )

# Chain cards
chain_cards = ""
for chain, rests in sorted(chain_restaurants.items(), key=lambda x: -len(x[1])):
    chain_slug = slugify(chain)
    chain_cards += (
        f'<a href="/chains/{chain_slug}/" class="browse-card chain">'
        f'<span class="bc-name">{chain.title()}</span>'
        f'<span class="bc-count">{len(rests)} locations</span>'
        f'</a>'
    )

# London neighbourhood cards
london_hood_cards = ""
for hood, count in london_hood_counts[:8]:
    london_hood_cards += (
        f'<a href="/cities/london#{hood["id"]}" class="browse-card london">'
        f'<span class="bc-name">{hood["name"]}</span>'
        f'<span class="bc-count">{count} restaurants</span>'
        f'</a>'
    )

# Dine-in vs takeaway
dine_pct = round(dine_in_total / total * 100, 1)
take_pct = round(takeaway_total / total * 100, 1)

SOFT_STAR = STAR_ENTITY

HTML = f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UK Thai Restaurant Directory — {total:,} Verified Listings | ThaiData</title>
    <meta name="description" content="Browse {total:,} FSA-verified Thai restaurants across {cities_count} UK cities. Complete with hygiene ratings, addresses, and inspection scores from the Food Standards Agency.">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="https://thaidata.uk/r/">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://thaidata.uk/r/">
    <meta property="og:title" content="UK Thai Restaurant Directory — {total:,} Verified Listings">
    <meta property="og:description" content="{total:,} Thai restaurants across {cities_count} UK cities. FSA hygiene ratings, inspection scores, and free business listings.">
    <meta property="og:locale" content="en_GB">
    <link rel="icon" type="image/png" sizes="32x32" href="/favicon-emblem.3a4d8ed8.png">
<link rel="apple-touch-icon" href="/apple-touch-emblem.1bde2e82.png">

    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" media="print" onload="this.media='all'"><noscript><!-- fa --></noscript>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">

    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "CollectionPage",
      "name": "UK Thai Restaurant Directory",
      "description": "{total:,} FSA-verified Thai restaurants across {cities_count} UK cities.",
      "url": "https://thaidata.uk/r/"
    }}
    </script>
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        {{ "@type": "ListItem", "position": 1, "name": "Home", "item": "https://thaidata.uk/" }},
        {{ "@type": "ListItem", "position": 2, "name": "Restaurant Directory", "item": "https://thaidata.uk/r/" }}
      ]
    }}
    </script>

    <style>
        :root {{ --c1: #A3132B; --c2: #A3132B; --dark: #FFFFFF; --ink: #1A1614; --ink2: #4A403C; --ink3: #7A6F6A; --ink4: #9C918C; --line: #E7DFD5; --bg: #FBF7F0; --card-bg: #FFFFFF; }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        img, svg, video {{ max-width: 100%; height: auto; }}
        body {{ font-family: 'Inter', system-ui, sans-serif; color: var(--ink); background: var(--bg); line-height: 1.6; -webkit-font-smoothing: antialiased; overflow-x: hidden; }}
        .grain {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: url("/assets/noise.svg"); opacity: 0.03; pointer-events: none; z-index: 999; }}
        .wrap {{ max-width: 960px; margin: 0 auto; padding: 0 20px; }}
        nav {{ background: var(--dark); border-bottom: 1px solid var(--line); height: 72px; display: flex; align-items: center; position: sticky; top: 0; z-index: 100; }}
        .nav-bar {{ max-width: 960px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; padding: 0 20px; width: 100%; }}
        .logo {{ display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 1.3rem; color: var(--ink); text-decoration: none; }}
        .logo-icon {{ height: 32px; width: auto; }}
        .hamburger {{ display: none; background: none; border: none; color: var(--ink); font-size: 1.5rem; cursor: pointer; }}
        .nav-links {{ display: flex; gap: 20px; align-items: center; }}
        .nav-links a {{ color: var(--ink4); text-decoration: none; font-size: 0.85rem; transition: color 0.2s; }}
        .nav-links a:hover {{ color: var(--ink); }}
        @media(max-width:768px) {{ .hamburger {{ display: block; }} .nav-links {{ display: none; position: absolute; top: 72px; left: 0; right: 0; background: var(--dark); border-bottom: 1px solid var(--line); flex-direction: column; padding: 16px 20px; gap: 14px; }} .nav-links.open {{ display: flex; }} }}

        .hero {{ padding: 60px 0 30px; text-align: center; }}
        .hero h1 {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: clamp(2rem, 5vw, 2.8rem); font-weight: 800; line-height: 1.15; margin-bottom: 12px; }}
        .hero h1 em {{ font-style: normal; color: var(--c2); }}
        .hero .sub {{ color: var(--ink4); font-size: 1rem; max-width: 560px; margin: 0 auto; line-height: 1.7; }}

        .intro {{ margin: 24px 0 32px; }}
        .intro p {{ color: var(--ink3); line-height: 1.7; margin-bottom: 10px; font-size: 0.92rem; }}

        .stats-row {{ display: flex; gap: 16px; justify-content: center; flex-wrap: wrap; margin: 20px 0; }}
        .stat-pill {{ background: var(--card-bg); border: 1px solid var(--line); border-radius: 12px; padding: 14px 20px; text-align: center; min-width: 90px; }}
        .stat-pill .num {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: 1.5rem; color: var(--c2); font-weight: 800;}}
        .stat-pill .lbl {{ color: var(--ink4); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; margin-top: 2px; }}

        .section {{ margin: 36px 0; }}
        .section h2 {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: 1.4rem; font-weight: 800; margin-bottom: 4px; }}
        .section h2 em {{ font-style: normal; color: var(--c2); }}
        .section .subtitle {{ color: var(--ink4); font-size: 0.88rem; margin-bottom: 14px; }}

        .browse-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }}
        .browse-card {{ display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; background: var(--card-bg); border: 1px solid var(--line); border-radius: 12px; text-decoration: none; transition: border-color 0.2s; }}
        .browse-card:hover {{ border-color: var(--c2); }}
        .browse-card .bc-name {{ font-weight: 500; font-size: 0.88rem; color: var(--ink); }}
        .browse-card .bc-count {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: 0.95rem; color: var(--c2); font-weight: 800;}}
        .browse-card.chain .bc-count {{ font-size: 0.78rem; color: var(--ink3); }}
        .browse-card.london {{ border-left: 2px solid var(--c2); }}

        .rest-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 10px; }}
        .rest-link {{ display: flex; align-items: center; gap: 8px; padding: 10px 14px; background: var(--card-bg); border: 1px solid var(--line); border-radius: 10px; text-decoration: none; transition: border-color 0.2s; }}
        .rest-link:hover {{ border-color: var(--c2); }}
        .rest-link .rl-name {{ font-weight: 500; font-size: 0.85rem; color: var(--ink); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        .rest-link .rl-city {{ font-size: 0.75rem; color: var(--ink4); }}
        .rest-link .rl-type {{ font-size: 0.7rem; color: var(--ink3); padding: 2px 8px; border: 1px solid var(--line); border-radius: 50px; }}

        .info-card {{ background: var(--card-bg); border: 1px solid var(--line); border-radius: 14px; padding: 24px; margin: 16px 0; }}
        .info-card h3 {{ font-size: 0.95rem; color: var(--ink); margin-bottom: 8px; }}
        .info-card p {{ color: var(--ink3); font-size: 0.88rem; line-height: 1.7; }}

        .cta {{ text-align: center; padding: 30px 0 40px; }}
        .cta a {{ display: inline-block; background: var(--c2); color: white; padding: 14px 28px; border-radius: 50px; font-weight: 700; text-decoration: none; font-size: 0.95rem; }}
        .cta a:hover {{ background: var(--c1); }}
        .cta .sec {{ background: transparent; border: 1px solid var(--line); margin-left: 10px; }}
        .cta .sec:hover {{ border-color: var(--c2); }}

        footer {{ text-align: center; padding: 30px 0 50px; border-top: 1px solid var(--line); color: var(--ink4); font-size: 0.8rem; margin-top: 40px; }}
        footer a {{ color: var(--ink4); text-decoration: none; }}
        footer a:hover {{ color: var(--ink); }}
    </style>
</head>
<body>
    <div class="grain"></div>
    <nav>
        <div class="nav-bar">
            <a href="/index.html" class="logo"><img src="/thaidata-lockup.b89c5cf2.png" alt="ThaiData UK" class="logo-icon" width="146" height="36"></a>
            <button class="hamburger" onclick="toggleMenu()" aria-label="Menu">&#9776;</button>
            <div class="nav-links">
                <a href="/index.html">Home</a>
                <a href="/guides.html">Guides</a>
                <a href="/pubs/">Pub Kitchens</a>
                <a href="/thai-restaurants-city-breakdown-uk">Cities</a>
                <a href="/claim/">Claim Listing</a>
            </div>
        </div>
    </nav>

    <div class="wrap">

        <div class="hero">
            <h1>UK Thai <em>Restaurant</em> Directory</h1>
            <p class="sub">Every FSA-listed Thai restaurant in the UK, in one place. {total:,} verified listings across {cities_count} cities, with hygiene ratings from the Food Standards Agency.</p>
        </div>

        <div class="stats-row">
            <div class="stat-pill"><div class="num">{total:,}</div><div class="lbl">Restaurants</div></div>
            <div class="stat-pill"><div class="num">{cities_count}</div><div class="lbl">Cities</div></div>
            <div class="stat-pill"><div class="num">{SOFT_STAR}{avg_overall}</div><div class="lbl">Avg Rating</div></div>
            <div class="stat-pill"><div class="num">{five_star}</div><div class="lbl">{five_pct}% Five-Star</div></div>
            <div class="stat-pill"><div class="num">{dine_in_total:,}</div><div class="lbl">Dine-in</div></div>
            <div class="stat-pill"><div class="num">{takeaway_total:,}</div><div class="lbl">Takeaways</div></div>
            <div class="stat-pill"><div class="num">{pubs_total}</div><div class="lbl">Pub Kitchens</div></div>
        </div>

        <div class="intro">
            <p>This directory covers <strong>all {total:,} FSA-listed Thai restaurants and takeaways</strong> in the United Kingdom. Every listing includes an official hygiene rating from the Food Standards Agency (FHRS) or Food Standards Scotland (FHIS), along with address, postcode, and type classification.</p>
            <p>Each restaurant has its own page at <strong>/r/[city]/[name]/</strong> with full inspection scores, a map location, and FSA hygiene detail breakdowns. If you own one of these restaurants, you can <a href="/claim/" style="color:var(--c2);">claim the listing</a> to add photos, opening hours, and contact details.</p>
        </div>

        <!-- Browse by city -->
        <div class="section">
            <h2>Browse by <em>City</em></h2>
            <p class="subtitle">The UK's biggest Thai restaurant markets. Each city has a full guide with neighbourhood breakdowns, chain data, and top picks.</p>
            <div class="browse-grid">
                {top_city_cards}
            </div>
            <p style="margin-top:10px;font-size:0.85rem;color:var(--ink4);">
                <a href="/thai-restaurants-city-breakdown-uk" style="color:var(--c2);">View all {cities_count} cities with Thai restaurants</a>
            </p>
        </div>

        <!-- London neighbourhoods -->
        <div class="section">
            <h2>London <em>Neighbourhoods</em></h2>
            <p class="subtitle">London has {len(london_restaurants)} Thai restaurants spread across its neighbourhoods. Jump to a specific area:</p>
            <div class="browse-grid">
                {london_hood_cards}
            </div>
            <p style="margin-top:10px;font-size:0.85rem;color:var(--ink4);">
                <a href="/cities/london" style="color:var(--c2);">Full London neighbourhood guide</a>
            </p>
        </div>

        <!-- Top rated -->
        <div class="section">
            <h2>Top-Rated <em>Restaurants</em></h2>
            <p class="subtitle">All with perfect {SOFT_STAR}5/5 FSA hygiene ratings. Click through for full inspection scores and maps.</p>
            <div class="rest-grid">
                {top_rated_html}
            </div>
        </div>

        <!-- By chain -->
        <div class="section">
            <h2>Browse by <em>Chain</em></h2>
            <p class="subtitle">Major UK Thai chains with dedicated profile pages showing all locations, average ratings, and market presence.</p>
            <div class="browse-grid">
                {chain_cards}
            </div>
            <p style="margin-top:10px;font-size:0.85rem;color:var(--ink4);">
                <a href="/chains/" style="color:var(--c2);">View all chain profiles</a>
            </p>
        </div>

        <!-- Dine-in vs takeaway -->
        <div class="section">
            <h2>Dine-In or <em>Takeaway</em></h2>
            <p class="subtitle">Of {total:,} Thai businesses, {dine_in_total:,} ({dine_pct}%) are dine-in restaurants and {takeaway_total:,} ({take_pct}%) are takeaways. Each city guide breaks down the split locally.</p>
            <div class="info-card">
                <h3>Dine-in restaurants {SOFT_STAR}</h3>
                <p>Full-service Thai restaurants offering sit-down dining. These make up the majority of the market and tend to have the highest hygiene ratings. Most are independent, family-run operations.</p>
            </div>
            <div class="info-card">
                <h3>Thai takeaways &#128717;</h3>
                <p>Takeaway-focused businesses, often operating from smaller premises. Particularly common in cities with large student populations and suburban areas where delivery demand is high.</p>
            </div>
        </div>

        <!-- Thai kitchens in pubs -->
        <div class="section">
            <h2>Thai <em>Kitchens</em> in Pubs</h2>
            <p class="subtitle">{pubs_total} Thai kitchens cook inside UK pubs — registered under the pub's own name, so they never show up in a normal restaurant search. We track them separately.</p>
            <div class="browse-grid">
                <a href="/pubs/" class="browse-card"><span class="bc-name">All pub kitchens</span><span class="bc-count">{pubs_total}</span></a>
            </div>
        </div>

        <!-- Data freshness -->
        <div class="section">
            <h2>About This <em>Directory</em></h2>
            <p class="subtitle">How the data is collected, verified, and kept current.</p>
            <div class="info-card">
                <p><strong>Data source:</strong> All ratings come from the Food Standards Agency (FHRS) and Food Standards Scotland (FHIS) -- official hygiene inspection scores from local authority visits.</p>
                <p style="margin-top:8px;"><strong>Coverage:</strong> We track every FSA-listed business in England, Wales, Scotland, and Northern Ireland that self-identifies as Thai cuisine. This includes restaurants, takeaways, cafes, and mobile caterers.</p>
                <p style="margin-top:8px;"><strong>Updates:</strong> The directory refreshes weekly from the FSA API. Each restaurant page shows its inspection date, so you know exactly how fresh the rating is.</p>
                <p style="margin-top:8px;"><strong>Accuracy:</strong> Business names and types come from the FSA register. Some businesses may have changed name or closed since their last inspection. Always call ahead.</p>
            </div>
        </div>

        <div class="cta">
            <a href="/thai-restaurants-city-breakdown-uk">Browse by city</a>
            <a href="/claim/" class="sec">Claim your listing</a>
        </div>

    </div>

    <footer>
        <p>Data sourced from the <a href="https://ratings.food.gov.uk" target="_blank" rel="noopener">Food Standards Agency</a>. Last updated {data.get("updated", "2026")}.</p>
        <p style="margin-top:6px;"><a href="/data-quality">Data Quality</a> &middot; <a href="/sitemap-page">Sitemap</a></p>
    </footer>

    <script>function toggleMenu(){{document.querySelector('.nav-links').classList.toggle('open');}}</script>
</body>
</html>
"""

# Fix ampersand issue in the info card
HTML = HTML.replace("&#128717;", "&#128717;")  # takeaway emoji entity

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
with open(OUTPUT, "w") as f:
    f.write(site_icons.transform(HTML))

kb = len(HTML) // 1024
print(f"Generated restaurant directory hub: {OUTPUT}")
print(f"  {kb}KB (was 7.5KB)")
print(f"  Top cities linked: {len(top_cities)}")
print(f"  Top-rated restaurants linked: {len(top_rated[:12])}")
print(f"  Chains linked: {len(chain_restaurants)}")
print(f"  London neighbourhoods: {len(london_hood_counts[:8])}")
print(f"  Stats row: {total:,} restaurants, {cities_count} cities, {pubs_total} pub kitchens")
