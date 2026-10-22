#!/usr/bin/env python3
"""Generate the pub-kitchens index at /pubs/index.html.

Thai kitchens that cook inside UK pubs (FSA type 7843). They are registered under
the pub's own name, so they are invisible to restaurant searches — this page gives
them a home, listed by city, separate from the main restaurant directory.
"""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any
import site_icons  # noqa: E402  (same-dir module, replaces Font Awesome)

REPO = Path(__file__).resolve().parent.parent
OUTPUT = REPO / "pubs" / "index.html"

with open(REPO / "data" / "restaurants.json") as f:
    data = json.load(f)

all_records = data["restaurants"]

# Load exclusions (moderation layer)
excluded_ids: set[int] = set()
excl_path = REPO / "data" / "exclusions.json"
if excl_path.exists():
    with open(excl_path) as f:
        excluded_ids.update(json.load(f).get("excluded_fsa_ids", []))

pubs = [r for r in all_records if r.get("type") == "pub" and r["id"] not in excluded_ids]


def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s)
    return s.strip("-")


def _scan_page_paths(root: Path) -> dict[str, tuple[str, str]]:
    paths: dict[str, tuple[str, str]] = {}
    for city_dir in os.scandir(root):
        if not city_dir.is_dir():
            continue
        for page_dir in os.scandir(city_dir.path):
            index = os.path.join(page_dir.path, "index.html")
            if not page_dir.is_dir() or not os.path.isfile(index):
                continue
            try:
                with open(index, encoding="utf-8") as fh:
                    m = re.search(r'fsa-id" content="(\d+)"', fh.read(4000))
            except OSError:
                continue
            if m and m.group(1) not in paths:
                paths[m.group(1)] = (city_dir.name, page_dir.name)
    return paths


page_paths = _scan_page_paths(REPO / "r")


def pub_url(r: dict[str, Any]) -> str:
    hit = page_paths.get(str(r["id"]))
    city_slug, dir_slug = hit if hit else (slugify(r["city"]), slugify(r["name"]))
    return f"/r/{city_slug}/{dir_slug}/"


# Group by city
by_city: dict[str, list[dict[str, Any]]] = defaultdict(list)
for r in pubs:
    by_city[r["city"]].append(r)

city_groups = sorted(by_city.items(), key=lambda kv: (-len(kv[1]), kv[0]))
n_pubs = len(pubs)
n_cities = len(city_groups)

ratings = [int(r["hygiene_rating"]) for r in pubs if str(r.get("hygiene_rating", "")).isdigit()]
avg = round(sum(ratings) / len(ratings), 1) if ratings else 0
five = sum(1 for r in ratings if r == 5)

STAR = "&#9733;"

# City sections
sections_html = ""
for city, rows in city_groups:
    rows.sort(key=lambda r: (-(int(r["hygiene_rating"]) if str(r.get("hygiene_rating", "")).isdigit() else 0),
                             r["name"].lower()))
    links = ""
    for r in rows:
        rating = str(r.get("hygiene_rating", ""))
        chip = f"Pub &middot; {STAR}{rating}" if rating.isdigit() else f"Pub &middot; {rating}"
        links += (
            f'<a href="{pub_url(r)}" class="rest-link">'
            f'<span class="rl-name">{r["name"]}</span>'
            f'<span class="rl-city">{r.get("postcode", "") or r["city"]}</span>'
            f'<span class="rl-type">{chip}</span>'
            f'</a>'
        )
    sections_html += (
        f'<div class="section">'
        f'<h3 style="font-size:1rem;margin-bottom:10px;">{city} <span style="color:var(--ink4);font-weight:400;font-size:0.85rem;">({len(rows)})</span></h3>'
        f'<div class="rest-grid">{links}</div>'
        f'</div>'
    )

HTML = f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Thai Kitchens in Pubs — {n_pubs} UK Pub Kitchens | ThaiData</title>
    <meta name="description" content="Thai kitchens cooking inside {n_pubs} UK pubs across {n_cities} areas. Found via pub registrations — FSA hygiene ratings, addresses, and links.">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="https://thaidata.uk/pubs/">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://thaidata.uk/pubs/">
    <meta property="og:title" content="Thai Kitchens in Pubs — {n_pubs} UK Pub Kitchens | ThaiData">
    <meta property="og:description" content="{n_pubs} Thai kitchens inside UK pubs, with FSA hygiene ratings and addresses.">
    <meta property="og:locale" content="en_GB">
    <link rel="icon" type="image/svg+xml" href="/favicon-lotus.8b83823b.svg">
    <link rel="icon" type="image/png" sizes="32x32" href="/favicon-lotus.png">
    <link rel="apple-touch-icon" href="/apple-touch-icon.28780c9a.png">

    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" media="print" onload="this.media='all'"><noscript><!-- fa --></noscript>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">

    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "CollectionPage",
      "name": "Thai Kitchens in Pubs",
      "description": "{n_pubs} Thai kitchens cooking inside UK pubs.",
      "url": "https://thaidata.uk/pubs/"
    }}
    </script>
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        {{ "@type": "ListItem", "position": 1, "name": "Home", "item": "https://thaidata.uk/" }},
        {{ "@type": "ListItem", "position": 2, "name": "Pub Kitchens", "item": "https://thaidata.uk/pubs/" }}
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
        .hero .sub {{ color: var(--ink4); font-size: 1rem; max-width: 620px; margin: 0 auto; line-height: 1.7; }}

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
        .section h3 {{ font-family:'Archivo','Inter',system-ui,sans-serif; }}

        .rest-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 10px; }}
        .rest-link {{ display: flex; align-items: center; gap: 8px; padding: 10px 14px; background: var(--card-bg); border: 1px solid var(--line); border-radius: 10px; text-decoration: none; transition: border-color 0.2s; }}
        .rest-link:hover {{ border-color: var(--c2); }}
        .rest-link .rl-name {{ font-weight: 500; font-size: 0.85rem; color: var(--ink); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        .rest-link .rl-city {{ font-size: 0.75rem; color: var(--ink4); }}
        .rest-link .rl-type {{ font-size: 0.7rem; color: var(--ink3); padding: 2px 8px; border: 1px solid var(--line); border-radius: 50px; white-space: nowrap; }}

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
            <a href="/index.html" class="logo"><img src="/thaidata-lockup.svg" alt="ThaiData" class="logo-icon" width="100" height="36"></a>
            <button class="hamburger" onclick="toggleMenu()" aria-label="Menu">&#9776;</button>
            <div class="nav-links">
                <a href="/index.html">Home</a>
                <a href="/guides.html">Guides</a>
                <a href="/r/">Restaurants</a>
                <a href="/thai-restaurants-city-breakdown-uk">Cities</a>
                <a href="/claim/">Claim Listing</a>
            </div>
        </div>
    </nav>

    <div class="wrap">

        <div class="hero">
            <h1>Thai <em>Kitchens</em> in Pubs</h1>
            <p class="sub">{n_pubs} Thai kitchens cooking inside UK pubs across {n_cities} areas — registered under the pub's own name, so they never show up in a normal restaurant search.</p>
        </div>

        <div class="stats-row">
            <div class="stat-pill"><div class="num">{n_pubs}</div><div class="lbl">Pub Kitchens</div></div>
            <div class="stat-pill"><div class="num">{n_cities}</div><div class="lbl">Areas</div></div>
            <div class="stat-pill"><div class="num">{STAR}{avg}</div><div class="lbl">Avg Rating</div></div>
            <div class="stat-pill"><div class="num">{five}</div><div class="lbl">Five-Star</div></div>
        </div>

        <div class="intro">
            <p>Some of the UK's best Thai food is cooked <strong>inside a pub kitchen</strong> — and you'd never find it by searching for Thai restaurants, because the business is registered under the pub's own name. This page lists every FSA-listed pub with a Thai kitchen we've verified, each with its own detail page and hygiene rating.</p>
            <p>Know a pub with a Thai kitchen that's missing? <a href="/contact" style="color:var(--c2);">Tell us</a> and we'll check it against the FSA register.</p>
        </div>

        <div class="section">
            <h2>All Pub <em>Kitchens</em></h2>
            <p class="subtitle">Grouped by area, best rated first. Each links to a full page with FSA hygiene details and a map.</p>
            {sections_html}
        </div>

        <div class="section">
            <h2>Why <em>Separate</em>?</h2>
            <div class="info-card">
                <p>Thai kitchens in pubs usually trade under the pub's name (for example <em>Thai Plough</em> or <em>Cricketers Thai</em>), and the FSA record is registered to the pub. That means they're invisible to standard restaurant listings and name searches for "Thai". We search the FSA register by business type to find them — so the main <a href="/r/" style="color:var(--c2);">restaurant directory</a> stays clean, and pub kitchens get their own section here.</p>
                <p style="margin-top:10px;"><i class="fas fa-beer-mug-empty" style="color:var(--c2);"></i> Thinking of running a Thai kitchen in a pub yourself? <a href="/learn/thai-kitchen-in-a-pub" style="color:var(--c2);">Read the guide to how it works</a> — deals, registration, tax and licensing.</p>
            </div>
        </div>

        <div class="cta">
            <a href="/r/">Browse all restaurants</a>
            <a href="/claim/" class="sec">Claim your listing</a>
        </div>

    </div>

    <footer>
        <p>Data sourced from the <a href="https://ratings.food.gov.uk" target="_blank" rel="noopener">Food Standards Agency</a>. Last updated {data.get("updated", "2026")}.</p>
        <p style="margin-top:6px;"><a href="/r/">Restaurant Directory</a> &middot; <a href="/data-quality">Data Quality</a> &middot; <a href="/sitemap-page">Sitemap</a></p>
    </footer>

    <script>function toggleMenu(){{document.querySelector('.nav-links').classList.toggle('open');}}</script>
</body>
</html>
"""

os.makedirs(OUTPUT.parent, exist_ok=True)
with open(OUTPUT, "w") as f:
    f.write(site_icons.transform(HTML))

print(f"Generated pub kitchens index: {OUTPUT}")
print(f"  {n_pubs} pub kitchens, {n_cities} areas, avg {STAR}{avg}, {five} five-star")
