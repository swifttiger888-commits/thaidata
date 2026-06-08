#!/usr/bin/env python3
"""Generate the city pillar hub page at /thai-restaurants-city-breakdown-uk.

This is the authority hub for all 253 city guides.
Links to every /cities/[slug] page with descriptive anchors.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

OUTPUT = REPO / "thai-restaurants-city-breakdown-uk.html"

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

# Group by city (excluding moderated venues)
by_city: dict[str, list[dict[str, Any]]] = defaultdict(list)
for r in restaurants:
    if r["id"] in excluded_ids:
        continue
    by_city[r["city"]].append(r)

def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s)
    return s.strip("-")

def compute_stats(rests: list[dict[str, Any]]) -> dict[str, Any]:
    ratings = [int(r["hygiene_rating"]) for r in rests if r.get("hygiene_rating", "").isdigit()]
    return {
        "count": len(rests),
        "dine_in": sum(1 for r in rests if r["type"] == "restaurant"),
        "takeaway": sum(1 for r in rests if r["type"] == "takeaway"),
        "avg": round(sum(ratings) / len(ratings), 1) if ratings else 0,
        "five": sum(1 for r in ratings if r == 5),
    }

# Compute all city stats
city_entries: list[dict[str, Any]] = []
for city, rests in by_city.items():
    s = compute_stats(rests)
    s["name"] = city
    s["slug"] = slugify(city)
    city_entries.append(s)

# Sort: London first, then by count descending
london_entry = next(c for c in city_entries if c["name"] == "London")
others = sorted([c for c in city_entries if c["name"] != "London"], key=lambda x: -x["count"])

# Enriched cities (threshold 13-35)
ENRICHED_COUNT_MIN = 13
enriched = [c for c in others if c["count"] >= ENRICHED_COUNT_MIN]
standard = [c for c in others if c["count"] < ENRICHED_COUNT_MIN]

total = sum(c["count"] for c in city_entries)
total_ratings = []
for r in restaurants:
    if r.get("hygiene_rating", "").isdigit():
        total_ratings.append(int(r["hygiene_rating"]))
avg_overall = round(sum(total_ratings) / len(total_ratings), 1) if total_ratings else 0
five_overall = sum(1 for r in total_ratings if r == 5)

# ── HTML generation ────────────────────────────────────────────────────────────

STAR = "&#9733;"

def star_string(rating: float) -> str:
    full = int(rating)
    half = 1 if rating - full >= 0.5 else 0
    return STAR * full + ("&#189;" if half else "")

def city_link(c: dict[str, Any]) -> str:
    rating_str = f"{STAR}{c['avg']}"
    return (
        f'<a href="/cities/{c["slug"]}" class="city-row">'
        f'<span class="city-name">{c["name"]}</span>'
        f'<span class="city-count">{c["count"]}</span>'
        f'<span class="city-rating">{rating_str}</span>'
        f'<span class="city-type">{c["dine_in"]} dine-in, {c["takeaway"]} takeaway</span>'
        f'<span class="city-five">{c["five"]}&#9733;</span>'
        f'</a>'
    )

# Featured: London + top enriched cities
featured_html = "".join(
    city_link(c) for c in [london_entry] + enriched[:8]
)

# Full directory: enriched + standard
enriched_html = "".join(city_link(c) for c in enriched)
standard_html = "".join(city_link(c) for c in standard[:100])  # first 100, rest in collapsed section

# Key stats
london_dine_in = london_entry["dine_in"]
london_takeaway = london_entry["takeaway"]
enriched_count = len(enriched) + 1  # + London
standard_count = len(standard)

# Top 5 five-star cities
top5_five = sorted(city_entries, key=lambda x: (-x["five"], -x["count"]))[:5]

# Best-rated cities (minimum 10 businesses)
best_rated = sorted([c for c in city_entries if c["count"] >= 10], key=lambda x: -x["avg"])[:8]

# Market opportunity (large population, low density)
# We don't have real population data here, so highlight cities with high count but room to grow
opportunity_cities = sorted([c for c in city_entries if 10 <= c["count"] <= 25], key=lambda x: (-x["count"], -x["avg"]))[:6]

HTML = f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UK Thai Restaurant Market: City-by-City Breakdown 2026 | ThaiData</title>
    <meta name="description" content="Complete city-by-city analysis of {total} FSA-registered Thai restaurants across all UK cities. Per-capita density, hygiene ratings, market gaps, and full directory with links to every city guide.">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="https://thaidata.uk/thai-restaurants-city-breakdown-uk">

    <meta property="og:type" content="article">
    <meta property="og:url" content="https://thaidata.uk/thai-restaurants-city-breakdown-uk">
    <meta property="og:title" content="UK Thai Restaurant Market: City-by-City Breakdown 2026">
    <meta property="og:description" content="{total} FSA-registered Thai businesses across all UK cities. Full directory with hygiene ratings, market gaps, and links to every city guide.">
    <meta property="og:image" content="https://thaidata.uk/thaidataukhero.webp">
    <meta property="og:locale" content="en_GB">

    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "Dataset",
      "name": "UK Thai Restaurant City Breakdown 2026",
      "description": "City-by-city analysis of {total} FSA-registered Thai restaurants and takeaways across {len(city_entries)} UK cities. Includes Scotland (FHIS), chain restaurants, per-capita density, and hygiene ratings.",
      "url": "https://thaidata.uk/thai-restaurants-city-breakdown-uk",
      "creator": {{ "@type": "Organization", "name": "ThaiData UK" }},
      "temporalCoverage": "2026-06-01/2026-06-30",
      "spatialCoverage": "United Kingdom",
      "license": "https://creativecommons.org/licenses/by/4.0/"
    }}
    </script>
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        {{ "@type": "ListItem", "position": 1, "name": "Home", "item": "https://thaidata.uk/" }},
        {{ "@type": "ListItem", "position": 2, "name": "Guides", "item": "https://thaidata.uk/guides" }},
        {{ "@type": "ListItem", "position": 3, "name": "UK Thai Restaurant Market: City-by-City Breakdown 2026" }}
      ]
    }}
    </script>

    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" media="print" onload="this.media='all'"><noscript><!-- fa --></noscript>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">

    <style>
        :root {{ --c1: #0A7A6F; --c2: #10B981; --dark: #0C1220; --ink: #0F172A; --ink2: #334155; --ink3: #64748B; --ink4: #94A3B8; --line: rgba(255,255,255,0.1); --bg: #0C1220; --card-bg: rgba(255,255,255,0.02); }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        img, svg, video {{ max-width: 100%; height: auto; }}
        body {{ font-family: 'Inter', system-ui, sans-serif; color: white; background: var(--bg); line-height: 1.6; -webkit-font-smoothing: antialiased; overflow-x: hidden; }}
        .grain {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: url("https://grainy-gradients.vercel.app/noise.svg"); opacity: 0.03; pointer-events: none; z-index: 999; }}
        .wrap {{ max-width: 1100px; margin: 0 auto; padding: 0 20px; }}
        nav {{ background: var(--dark); border-bottom: 1px solid var(--line); height: 72px; display: flex; align-items: center; position: sticky; top: 0; z-index: 100; }}
        .nav-bar {{ max-width: 1100px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; padding: 0 20px; width: 100%; }}
        .logo {{ display: flex; align-items: center; gap: 12px; font-weight: 700; font-size: 1.4rem; color: white; text-decoration: none; }}
        .logo-icon {{ height: 36px; width: auto; }}

        .hero {{ padding: 60px 0 30px; text-align: center; }}
        .hero h1 {{ font-family: 'Instrument Serif', serif; font-size: clamp(1.8rem, 5vw, 2.8rem); font-weight: 400; line-height: 1.15; margin-bottom: 14px; }}
        .hero h1 em {{ font-style: italic; color: var(--c2); }}
        .hero .sub {{ color: var(--ink4); font-size: 1rem; max-width: 640px; margin: 0 auto; line-height: 1.7; }}

        .intro {{ margin: 30px 0; }}
        .intro p {{ color: var(--ink3); line-height: 1.8; margin-bottom: 14px; font-size: 0.95rem; }}

        .section {{ margin: 40px 0; }}
        .section h2 {{ font-family: 'Instrument Serif', serif; font-size: 1.5rem; font-weight: 400; margin-bottom: 4px; }}
        .section h2 em {{ font-style: italic; color: var(--c2); }}
        .section .subtitle {{ color: var(--ink4); font-size: 0.9rem; margin-bottom: 20px; }}

        /* Stats bar */
        .stats-bar {{ display: flex; gap: 20px; justify-content: center; flex-wrap: wrap; margin: 24px 0; }}
        .stat-pill {{ background: var(--card-bg); border: 1px solid var(--line); border-radius: 12px; padding: 16px 24px; text-align: center; min-width: 110px; }}
        .stat-pill .num {{ font-family: 'Instrument Serif', serif; font-size: 1.6rem; color: var(--c2); }}
        .stat-pill .lbl {{ color: var(--ink4); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.06em; margin-top: 2px; }}

        /* City directory */
        .directory-header {{ display: grid; grid-template-columns: 3fr 1fr 1fr 2fr 1fr; gap: 8px; padding: 10px 16px; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--ink4); border-bottom: 1px solid var(--line); }}
        .directory-header span {{ text-align: center; }}
        .directory-header span:first-child {{ text-align: left; }}

        .city-row {{ display: grid; grid-template-columns: 3fr 1fr 1fr 2fr 1fr; gap: 8px; align-items: center; padding: 12px 16px; text-decoration: none; color: white; border-bottom: 1px solid rgba(255,255,255,0.04); transition: background 0.15s; }}
        .city-row:hover {{ background: rgba(255,255,255,0.04); }}
        .city-name {{ font-weight: 500; font-size: 0.9rem; }}
        .city-count {{ font-family: 'Instrument Serif', serif; font-size: 1.1rem; color: var(--c2); text-align: center; }}
        .city-rating {{ font-size: 0.85rem; color: var(--c2); text-align: center; }}
        .city-type {{ font-size: 0.8rem; color: var(--ink3); text-align: center; }}
        .city-five {{ font-size: 0.85rem; color: #FBBF24; text-align: center; }}
        .city-row.london {{ background: rgba(16,185,129,0.08); border-left: 3px solid var(--c2); border-radius: 0 8px 8px 0; }}

        /* Highlight boxes */
        .highlight-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px; }}
        .highlight-card {{ background: var(--card-bg); border: 1px solid var(--line); border-radius: 14px; padding: 24px; }}
        .highlight-card h3 {{ font-size: 0.9rem; color: white; margin-bottom: 8px; }}
        .highlight-card p {{ font-size: 0.85rem; color: var(--ink3); line-height: 1.6; }}
        .highlight-card strong {{ color: var(--c2); }}

        .featured-section {{ background: rgba(16,185,129,0.04); border: 1px solid rgba(16,185,129,0.15); border-radius: 16px; padding: 24px; margin: 30px 0; }}

        .cta {{ text-align: center; padding: 30px 0 50px; }}
        .cta a {{ display: inline-block; background: var(--c2); color: white; padding: 14px 30px; border-radius: 50px; font-weight: 700; text-decoration: none; }}
        .cta a:hover {{ background: var(--c1); }}

        footer {{ text-align: center; padding: 40px 0; border-top: 1px solid var(--line); color: var(--ink4); font-size: 0.85rem; }}
        footer a {{ color: var(--ink4); text-decoration: none; }}
        footer a:hover {{ color: white; }}
    </style>
</head>
<body>
    <div class="grain"></div>
    <nav>
        <div class="nav-bar">
            <a href="index.html" class="logo"><img src="/logo-horizontal.svg" alt="ThaiData" class="logo-icon" width="100" height="36"></a>
            <a href="/guides" style="color:rgba(255,255,255,0.6);font-size:0.9rem;text-decoration:none;">Guides</a>
        </div>
    </nav>

    <div class="wrap">

        <div class="hero">
            <h1>UK Thai Restaurant Market:<br><em>City-by-City</em> Breakdown 2026</h1>
            <p class="sub">{total} FSA-registered Thai businesses across {len(city_entries)} cities. London leads with {london_entry["count"]} restaurants. Here is the full directory with hygiene ratings, market data, and links to every city guide.</p>
        </div>

        <div class="stats-bar">
            <div class="stat-pill"><div class="num">{total}</div><div class="lbl">Total Thai Businesses</div></div>
            <div class="stat-pill"><div class="num">{len(city_entries)}</div><div class="lbl">Cities</div></div>
            <div class="stat-pill"><div class="num">{sum(c["dine_in"] for c in city_entries)}</div><div class="lbl">Dine-in Restaurants</div></div>
            <div class="stat-pill"><div class="num">{sum(c["takeaway"] for c in city_entries)}</div><div class="lbl">Takeaways</div></div>
            <div class="stat-pill"><div class="num">{STAR}{avg_overall}</div><div class="lbl">Avg Hygiene Rating</div></div>
            <div class="stat-pill"><div class="num">{five_overall}</div><div class="lbl">Five-Star</div></div>
        </div>

        <div class="intro">
            <p>This page is the starting point for exploring Thai restaurants across the United Kingdom. Every city below has a dedicated guide with neighbourhood breakdowns, top-rated restaurants, chain presence, and FSA hygiene data. Data is sourced from the <strong>Food Standards Agency</strong> (FHRS in England/Wales/NI, FHIS in Scotland) and updated weekly.</p>
            <p>London is the dominant market with {london_entry["count"]} businesses, but dozens of cities across the country have thriving Thai scenes. Use this directory to find your city, compare markets, or discover where the best-rated Thai food in the UK is.</p>
        </div>

        <!-- Key highlights -->
        <div class="section">
            <h2>Market <em>Highlights</em></h2>
            <p class="subtitle">Key findings from the latest FSA data across all UK cities.</p>
            <div class="highlight-grid">
                <div class="highlight-card">
                    <h3>Largest market</h3>
                    <p><strong>London</strong> with {london_entry["count"]} Thai businesses — {london_entry["dine_in"]} dine-in, {london_entry["takeaway"]} takeaways. {london_entry["five"]} hold a perfect {STAR}5 hygiene rating.</p>
                </div>
                <div class="highlight-card">
                    <h3>Highest five-star rate</h3>
                    <p><strong>{top5_five[0]["name"]}</strong> has {top5_five[0]["five"]} five-star businesses ({top5_five[0]["five"]}/{top5_five[0]["count"]} = {top5_five[0]["five"]/top5_five[0]["count"]*100:.0f}%). Also: {top5_five[1]["name"]} ({top5_five[1]["five"]}), {top5_five[2]["name"]} ({top5_five[2]["five"]}).</p>
                </div>
                <div class="highlight-card">
                    <h3>Best-rated (10+ businesses)</h3>
                    <p><strong>{best_rated[0]["name"]}</strong> (avg {STAR}{best_rated[0]["avg"]}/5), {best_rated[1]["name"]} ({STAR}{best_rated[1]["avg"]}), {best_rated[2]["name"]} ({STAR}{best_rated[2]["avg"]}).</p>
                </div>
                <div class="highlight-card">
                    <h3>Markets with room to grow</h3>
                    <p><strong>{opportunity_cities[0]["name"]}</strong> ({opportunity_cities[0]["count"]} restaurants, avg {STAR}{opportunity_cities[0]["avg"]}), {opportunity_cities[1]["name"]} ({opportunity_cities[1]["count"]}), {opportunity_cities[2]["name"]} ({opportunity_cities[2]["count"]}).</p>
                </div>
                <div class="highlight-card">
                    <h3>Scotland coverage</h3>
                    <p>Data includes FHIS-rated restaurants in Scotland. <strong>Edinburgh</strong> ({next(c["count"] for c in city_entries if c["name"] == "Edinburgh")}), <strong>Glasgow</strong> ({next((c["count"] for c in city_entries if c["name"] == "Glasgow"), 0)}), and cities across all Scottish local authorities.</p>
                </div>
                <div class="highlight-card">
                    <h3>Data freshness</h3>
                    <p>FSA data updated <strong>{data.get("updated", "weekly")}</strong>. Each city guide links to individual restaurant pages with full inspection scores.</p>
                </div>
            </div>
        </div>

        <!-- Featured directory -->
        <div class="featured-section">
            <h2 style="font-family:'Instrument Serif',serif;font-size:1.4rem;font-weight:400;margin-bottom:16px;">City <em>Directory</em></h2>
            <p style="color:var(--ink4);font-size:0.85rem;margin-bottom:16px;">Each row links to the full city guide with neighbourhood breakdowns, top-rated picks, chain data, and FAQ.</p>
            <div class="directory-header">
                <span>City</span>
                <span>Total</span>
                <span>Rating</span>
                <span>Dine-in / Takeaway</span>
                <span>{STAR}5</span>
            </div>
            <div id="city-directory">
                {featured_html}
                {enriched_html}
                {standard_html}
            </div>
            <button id="show-all-btn" onclick="document.getElementById('all-cities').style.display='block';this.style.display='none';" style="margin:16px auto 0;background:transparent;border:1px solid var(--line);color:var(--ink4);padding:10px 20px;border-radius:50px;cursor:pointer;font-size:0.85rem;">Show all {standard_count} smaller markets</button>
            <div id="all-cities" style="display:none;">
                {''.join(city_link(c) for c in standard[100:])}
            </div>
        </div>

        <div class="cta">
            <a href="/cities/london">Explore London's Thai scene</a>
            <span style="display:inline-block;margin:0 12px;color:var(--ink4);font-size:0.85rem;">or browse by city above</span>
            <a href="/r/" style="background:transparent;border:1px solid var(--line);">View individual restaurants</a>
        </div>

        {''}
        <div class="section">
            <h2>About This <em>Data</em></h2>
            <p class="subtitle">How we collect, verify, and present city-level Thai restaurant data.</p>
            <div class="highlight-grid">
                <div class="highlight-card">
                    <h3>Data source</h3>
                    <p>All ratings come from the <strong>Food Standards Agency</strong> (FHRS) and <strong>Food Standards Scotland</strong> (FHIS). Every rating is a hygiene inspection score from an official visit.</p>
                </div>
                <div class="highlight-card">
                    <h3>Coverage</h3>
                    <p>We track <strong>all FSA-registered</strong> businesses in England, Wales, Scotland, and Northern Ireland that identify as Thai cuisine. This includes restaurants, takeaways, and cafes.</p>
                </div>
                <div class="highlight-card">
                    <h3>Update frequency</h3>
                    <p>City data refreshes <strong>weekly</strong> from the FSA API. Each city guide shows a date badge so you know exactly how fresh the data is.</p>
                </div>
                <div class="highlight-card">
                    <h3>Accuracy</h3>
                    <p>Chain detection uses keyword matching against known UK Thai chains. Independent businesses may share names with chains in other regions. Data quibbles? Email us.</p>
                </div>
            </div>
        </div>

    </div>

    <footer>
        <div class="wrap">
            <p><a href="/">ThaiData</a> · Data from <a href="https://www.food.gov.uk/" target="_blank">Food Standards Agency</a> · Updated {data.get("updated", "2026")} · <a href="/data-quality">Methodology</a></p>
        </div>
    </footer>

</body>
</html>
"""

# Write
os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
with open(OUTPUT, "w") as f:
    f.write(HTML)

# Stats
linked_cities = len(featured_html.split("city-row")) + len(enriched_html.split("city-row")) + len(standard_html.split("city-row"))
kb = len(HTML) // 1024

print(f"Generated city hub: {OUTPUT}")
print(f"  {kb}KB, {linked_cities} cities linked")
print(f"  Featured: London + {len(enriched[:8])} enriched cities")
print(f"  Full directory: {len(enriched)} enriched + {standard_count} standard")
print(f"  6 market highlight cards")
print(f"  Internal links: all city pages linked from directory")
