#!/usr/bin/env python3
"""Generate the chain directory hub at /chains/index.html.

Connects chain profiles to city guides and individual restaurant pages.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any
import site_icons  # noqa: E402  (same-dir module, replaces Font Awesome)

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

OUTPUT = REPO / "chains" / "index.html"

with open(REPO / "data" / "restaurants.json") as f:
    data = json.load(f)

restaurants = data["restaurants"]
total_restaurants = len(restaurants)

def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s)
    return s.strip("-")

def rest_url(r: dict[str, Any]) -> str:
    city_slug = slugify(r["city"])
    name_slug = slugify(r["name"])
    return f"/r/{city_slug}/{name_slug}/"

# Chain keywords mapped to existing chain profile slugs
# Only include chains verifiable from FSA restaurant names
CHAIN_DEFS: list[dict[str, Any]] = [
    {"keywords": ["giggling squid"], "label": "Giggling Squid", "slug": "giggling-squid"},
    {"keywords": ["rosa's thai"], "label": "Rosa's Thai", "slug": "rosas-thai"},
    {"keywords": ["banana tree"], "label": "Banana Tree", "slug": "banana-tree"},
    {"keywords": ["thai express"], "label": "Thai Express", "slug": "thai-express"},
    {"keywords": ["thai square"], "label": "Thai Square", "slug": "thai-square"},
    {"keywords": ["thaikhun"], "label": "Thaikhun", "slug": "thaikhun"},
    {"keywords": ["busaba"], "label": "Busaba", "slug": "busaba"},
    {"keywords": ["sukhothai"], "label": "Sukhothai", "slug": "sukhothai"},
    {"keywords": ["camile thai"], "label": "Camile Thai", "slug": "camile-thai"},
    {"keywords": ["patara"], "label": "Patara", "slug": "patara-fine-thai-cuisine"},
    {"keywords": ["chaophraya"], "label": "Chaophraya", "slug": "chaophraya"},
    {"keywords": ["mango tree"], "label": "Mango Tree", "slug": "mango-tree"},
]

# Detect restaurants per chain
chain_data: list[dict[str, Any]] = []
for cd in CHAIN_DEFS:
    rests: list[dict[str, Any]] = []
    for r in restaurants:
        name_lower = r["name"].lower()
        for kw in cd["keywords"]:
            if kw in name_lower:
                rests.append(r)
                break

    # City breakdown
    by_city: dict[str, int] = defaultdict(int)
    for r in rests:
        by_city[r["city"]] += 1
    top_cities = sorted(by_city.items(), key=lambda x: -x[1])[:4]

    # Ratings
    ratings = [int(r["hygiene_rating"]) for r in rests if r.get("hygiene_rating", "").isdigit()]
    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0
    five_star = sum(1 for r in ratings if r == 5)

    # Sample links
    sample_rest = rests[0] if rests else None
    sample_url = rest_url(sample_rest) if sample_rest else ""

    cd["restaurants"] = rests
    cd["count"] = len(rests)
    cd["top_cities"] = top_cities
    cd["avg_rating"] = avg_rating
    cd["five_star"] = five_star
    cd["sample_url"] = sample_url
    cd["dine_in"] = sum(1 for r in rests if r["type"] == "restaurant")
    cd["takeaway"] = cd["count"] - cd["dine_in"]
    chain_data.append(cd)

# Sort by count descending
chain_data.sort(key=lambda x: -x["count"])

major = [c for c in chain_data if c["count"] >= 10]
regional = [c for c in chain_data if c["count"] < 10]

total_chain_restaurants = sum(c["count"] for c in chain_data)
total_chains = len(chain_data)

# ── HTML ──────────────────────────────────────────────────────────────────────

STAR_ENTITY = "&#9733;"

def chain_card(cd: dict[str, Any], featured: bool = False) -> str:
    cities_text = " &middot; ".join(
        f'<a href="/cities/{slugify(city)}" style="color:var(--c2);text-decoration:underline;text-underline-offset:3px;">{city}</a> ({n})'
        for city, n in cd["top_cities"]
    )
    sample_link = ""
    if cd["sample_url"]:
        sample_link = f'<a href="{cd["sample_url"]}" class="chain-sample">View sample location</a>'

    rating_text = f"{STAR_ENTITY}{cd['avg_rating']} avg ({cd['five_star']} five-star)" if cd["avg_rating"] else "No data"

    return f'''
    <div class="chain-card{' featured' if featured else ''}">
        <div class="chain-header">
            <h3>{cd["label"]}</h3>
            <span class="chain-count">{cd["count"]} locations</span>
        </div>
        <div class="chain-meta">
            <span class="chain-rating">{rating_text}</span>
            <span class="chain-split">{cd["dine_in"]} dine-in, {cd["takeaway"]} takeaway</span>
        </div>
        <div class="chain-cities">
            <span class="chain-cities-label">Top cities:</span>
            {cities_text}
        </div>
        <div class="chain-links">
            <a href="{cd["slug"]}.html" class="chain-profile-link">Full profile</a>
            {sample_link}
        </div>
    </div>
    '''


HTML = f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UK Thai Restaurant Chains — Complete Directory 2026 | ThaiData</title>
    <meta name="description" content="Complete directory of {total_chains} UK Thai restaurant chains verified from FSA data. {major[0]['count']} locations for {major[0]['label']}, plus {major[1]['label']}, {major[2]['label']} and more. City presence, hygiene ratings, and location maps.">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="https://thaidata.uk/chains/">
    <link rel="icon" type="image/svg+xml" href="/favicon-lotus.8b83823b.svg">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-lotus.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.28780c9a.png">

    <meta property="og:title" content="UK Thai Restaurant Chains — Complete Directory 2026 | ThaiData">
    <meta property="og:description" content="{total_chains} UK Thai restaurant chains with FSA-verified location data. City presence breakdowns, hygiene ratings, and sample location maps.">
    <meta property="og:url" content="https://thaidata.uk/chains/">
    <meta property="og:type" content="website">

    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "CollectionPage",
      "name": "UK Thai Restaurant Chains Directory",
      "description": "{total_chains} UK Thai restaurant chains with FSA-verified location data.",
      "url": "https://thaidata.uk/chains/"
    }}
    </script>
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        {{ "@type": "ListItem", "position": 1, "name": "Home", "item": "https://thaidata.uk/" }},
        {{ "@type": "ListItem", "position": 2, "name": "Restaurant Directory", "item": "https://thaidata.uk/r/" }},
        {{ "@type": "ListItem", "position": 3, "name": "Chain Directory", "item": "https://thaidata.uk/chains/" }}
      ]
    }}
    </script>

    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" media="print" onload="this.media='all'"><noscript><!-- fa --></noscript>

    <style>
        :root {{ --c1: #A3132B; --c2: #A3132B; --dark: #FFFFFF; --ink: #1A1614; --ink2: #4A403C; --ink3: #7A6F6A; --ink4: #9C918C; --line: #E7DFD5; --bg: #FBF7F0; --card-bg: #FFFFFF; }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        img, svg, video {{ max-width: 100%; height: auto; }}
        body {{ font-family: 'Inter', system-ui, sans-serif; color: var(--ink); background: var(--bg); line-height: 1.6; -webkit-font-smoothing: antialiased; overflow-x: hidden; }}
        .grain {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: url("/assets/noise.svg"); opacity: 0.03; pointer-events: none; z-index: 999; }}
        .wrap {{ max-width: 960px; margin: 0 auto; padding: 0 20px; }}
        nav {{ background: var(--dark); border-bottom: 1px solid var(--line); height: 72px; display: flex; align-items: center; position: sticky; top: 0; z-index: 100; }}
        .nav-bar {{ max-width: 960px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; padding: 0 20px; width: 100%; }}
        .logo {{ display: flex; align-items: center; gap: 12px; font-weight: 700; font-size: 1.3rem; color: var(--ink); text-decoration: none; }}
        .logo-icon {{ height: 36px; width: auto; }}
        .hamburger {{ display: none; background: none; border: none; color: var(--ink); font-size: 1.5rem; cursor: pointer; }}
        .nav-links {{ display: flex; gap: 20px; align-items: center; }}
        .nav-links a {{ color: var(--ink4); text-decoration: none; font-size: 0.85rem; transition: color 0.2s; }}
        .nav-links a:hover {{ color: var(--ink); }}
        @media(max-width:768px) {{ .hamburger {{ display: block; }} .nav-links {{ display: none; position: absolute; top: 72px; left: 0; right: 0; background: var(--dark); border-bottom: 1px solid var(--line); flex-direction: column; padding: 16px 20px; gap: 14px; }} .nav-links.open {{ display: flex; }} }}

        .hero {{ padding: 60px 0 30px; text-align: center; }}
        .hero h1 {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: clamp(2rem, 5vw, 2.8rem); font-weight: 800; line-height: 1.15; margin-bottom: 12px; }}
        .hero h1 em {{ font-style: normal; color: var(--c2); }}
        .hero .sub {{ color: var(--ink4); font-size: 1rem; max-width: 600px; margin: 0 auto; line-height: 1.7; }}

        .intro {{ margin: 24px 0 32px; }}
        .intro p {{ color: var(--ink3); line-height: 1.7; margin-bottom: 10px; font-size: 0.92rem; }}

        .stats-row {{ display: flex; gap: 16px; justify-content: center; flex-wrap: wrap; margin: 20px 0; }}
        .stat-pill {{ background: var(--card-bg); border: 1px solid var(--line); border-radius: 12px; padding: 14px 20px; text-align: center; min-width: 90px; }}
        .stat-pill .num {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: 1.5rem; color: var(--c2); font-weight: 800;}}
        .stat-pill .lbl {{ color: var(--ink4); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; margin-top: 2px; }}

        .section {{ margin: 40px 0; }}
        .section h2 {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: 1.4rem; font-weight: 800; margin-bottom: 4px; }}
        .section h2 em {{ font-style: normal; color: var(--c2); }}
        .section .subtitle {{ color: var(--ink4); font-size: 0.9rem; margin-bottom: 18px; }}

        .chain-card {{ background: var(--card-bg); border: 1px solid var(--line); border-radius: 14px; padding: 24px; margin: 14px 0; transition: border-color 0.2s; }}
        .chain-card:hover {{ border-color: rgba(16,185,129,0.3); }}
        .chain-card.featured {{ background: rgba(16,185,129,0.04); border-color: rgba(16,185,129,0.2); }}
        .chain-header {{ display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }}
        .chain-header h3 {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: 1.3rem; font-weight: 800; color: var(--ink); }}
        .chain-count {{ font-size: 0.85rem; color: var(--c2); font-weight: 600; }}
        .chain-meta {{ display: flex; gap: 16px; margin: 6px 0 10px; font-size: 0.82rem; color: var(--ink4); flex-wrap: wrap; }}
        .chain-rating {{ color: var(--c2); }}
        .chain-cities {{ font-size: 0.85rem; color: var(--ink3); line-height: 1.7; }}
        .chain-cities-label {{ color: var(--ink4); }}
        .chain-links {{ margin-top: 12px; display: flex; gap: 14px; flex-wrap: wrap; }}
        .chain-profile-link {{ display: inline-block; padding: 6px 16px; background: var(--c2); color: white; border-radius: 50px; font-size: 0.8rem; font-weight: 600; text-decoration: none; }}
        .chain-profile-link:hover {{ background: var(--c1); }}
        .chain-sample {{ display: inline-block; padding: 6px 16px; border: 1px solid var(--line); color: var(--ink3); border-radius: 50px; font-size: 0.8rem; text-decoration: none; }}
        .chain-sample:hover {{ border-color: var(--c2); color: var(--c2); }}

        .data-note {{ background: rgba(251,191,36,0.06); border: 1px solid rgba(251,191,36,0.15); border-radius: 12px; padding: 16px 20px; margin: 20px 0; font-size: 0.85rem; color: var(--ink3); line-height: 1.6; }}
        .data-note strong {{ color: var(--ink); }}

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
            <a href="/" class="logo"><img src="/thaidata-lockup.svg" alt="ThaiData" class="logo-icon" width="100" height="36"></a>
            <button class="hamburger" onclick="toggleMenu()" aria-label="Menu">&#9776;</button>
            <div class="nav-links">
                <a href="/guides.html">Guides</a>
                <a href="/thai-restaurants-city-breakdown-uk">Cities</a>
                <a href="/r/">Restaurants</a>
                <a href="/chains/" style="color: var(--ink);">Chains</a>
            </div>
        </div>
    </nav>

    <div class="wrap">

        <div class="hero">
            <h1>UK Thai Restaurant <em>Chains</em></h1>
            <p class="sub">{total_chains} major Thai restaurant chains verified from FSA data. Location counts, city presence, hygiene ratings, and links to individual restaurant pages.</p>
        </div>

        <div class="stats-row">
            <div class="stat-pill"><div class="num">{total_chains}</div><div class="lbl">Chains</div></div>
            <div class="stat-pill"><div class="num">{total_chain_restaurants}</div><div class="lbl">Chain Locations</div></div>
            <div class="stat-pill"><div class="num">{total_restaurants - total_chain_restaurants}</div><div class="lbl">Independent</div></div>
        </div>

        <div class="intro">
            <p>This directory covers the major UK Thai restaurant chains -- groups with multiple locations across the country. Each profile includes verified location counts from the <strong>Food Standards Agency</strong> register, city presence maps, and links to individual restaurant pages.</p>
            <p>Chain detection is based on <strong>FSA restaurant name matching</strong>, not company ownership data. Some chains may have additional locations under different trading names not captured here. Figures reflect FSA-listed businesses only.</p>
        </div>

        <!-- Major chains -->
        <div class="section">
            <h2>Major <em>Chains</em></h2>
            <p class="subtitle">Nationwide Thai restaurant groups with 10 or more FSA-listed locations.</p>
            {"".join(chain_card(c, featured=True) for c in major)}
        </div>

        <!-- Regional chains -->
        <div class="section">
            <h2>Regional <em>Chains</em></h2>
            <p class="subtitle">Smaller groups with strong local presence, typically under 10 locations.</p>
            {"".join(chain_card(c) for c in regional)}
        </div>

        <div class="data-note">
            <strong>About the data:</strong> Chain figures are based on FSA register name matching. Some businesses listed as chains may operate independently under a common name. Numbers represent FSA-listed locations only, not the chain's total estate. Always verify with the chain's own website. Data updated {data.get("updated", "2026")}.
        </div>

        <!-- Related links -->
        <div class="section">
            <h2>Related <em>Pages</em></h2>
            <p class="subtitle">Explore Thai restaurants across the UK by city, individual listing, or data report.</p>
            <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px;">
                <a href="/thai-restaurants-city-breakdown-uk" class="chain-card" style="text-decoration:none;display:block;">
                    <div class="chain-header"><h3 style="font-size:1rem;">Browse by City</h3></div>
                    <div style="font-size:0.8rem;color:var(--ink3);margin-top:6px;">All 254 UK cities with Thai restaurants</div>
                </a>
                <a href="/r/" class="chain-card" style="text-decoration:none;display:block;">
                    <div class="chain-header"><h3 style="font-size:1rem;">Restaurant Directory</h3></div>
                    <div style="font-size:0.8rem;color:var(--ink3);margin-top:6px;">All {total_restaurants:,} individual restaurant pages</div>
                </a>
                <a href="/chains/" class="chain-card" style="text-decoration:none;display:block;border-color:rgba(16,185,129,0.3);">
                    <div class="chain-header"><h3 style="font-size:1rem;">Chain Profiles</h3></div>
                    <div style="font-size:0.8rem;color:var(--ink3);margin-top:6px;">Full profiles with market analysis</div>
                </a>
            </div>
        </div>

    </div>

    <footer>
        <div class="wrap">
            <p>Data sourced from the <a href="https://ratings.food.gov.uk" target="_blank" rel="noopener">Food Standards Agency</a>. Chain detection via FSA register name matching. Updated {data.get("updated", "2026")}.</p>
            <p style="margin-top:6px;"><a href="/data-quality">Data Quality</a> &middot; <a href="/sitemap-page">Sitemap</a></p>
        </div>
    </footer>

    <script>function toggleMenu(){{document.querySelector('.nav-links').classList.toggle('open');}}</script>
</body>
</html>
"""

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
with open(OUTPUT, "w") as f:
    f.write(site_icons.transform(HTML))

kb = len(HTML) // 1024
print(f"Generated chain directory hub: {OUTPUT}")
print(f"  {kb}KB (was 7.2KB)")
print(f"  Major chains: {len(major)} ({[c['label'] + ' (' + str(c['count']) + ')' for c in major]})")
print(f"  Regional chains: {len(regional)} ({[c['label'] + ' (' + str(c['count']) + ')' for c in regional]})")
print(f"  Total FSA-verified chain locations: {total_chain_restaurants}")
print(f"  Links: city pages, chain profiles, sample /r/ pages")
