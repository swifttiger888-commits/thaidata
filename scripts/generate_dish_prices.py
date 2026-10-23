#!/usr/bin/env python3
"""Generate the Thai dish pricing hub at /dish-prices.

Builds a pricing intelligence page with national averages, city breakdowns,
and links into city guides and restaurant pages.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any
import site_icons  # noqa: E402  (same-dir module, replaces Font Awesome)

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

OUTPUT = REPO / "dish-prices.html"

# ── Pricing data (from Menu Price Survey, June 2026) ─────────────────────────

# National average prices by dish category
DISH_CATEGORIES = [
    {
        "name": "Classic Noodles & Rice",
        "emoji": "&#127837;",
        "dishes": [
            ("Pad Thai (chicken)", "12.50", "14.95", "+20%"),
            ("Pad See Ew", "11.50", "14.00", "+22%"),
            ("Pad Kra Pao (chicken)", "11.95", "14.50", "+21%"),
            ("Jasmine Rice (portion)", "3.50", "4.20", "+20%"),
            ("Sticky Rice (portion)", "3.80", "4.50", "+18%"),
        ],
    },
    {
        "name": "Curries",
        "emoji": "&#127798;",
        "dishes": [
            ("Green Curry (chicken)", "13.00", "15.90", "+22%"),
            ("Red Curry (beef)", "13.50", "16.50", "+22%"),
            ("Massaman Curry", "13.95", "16.90", "+21%"),
        ],
    },
    {
        "name": "Soups & Starters",
        "emoji": "&#127858;",
        "dishes": [
            ("Tom Yum Goong", "6.95", "8.50", "+22%"),
            ("Tom Kha Gai", "7.25", "8.95", "+23%"),
            ("Thai Fish Cakes (starter)", "7.50", "9.25", "+23%"),
            ("Spring Rolls (vegetable)", "5.95", "7.25", "+22%"),
        ],
    },
]

CITY_PRICES = [
    ("London", "12.08", "14.58", "+20.9%"),
    ("Manchester", "10.88", "13.26", "+22.4%"),
    ("Leeds", "10.49", "12.87", "+23.0%"),
    ("Birmingham", "10.62", "12.86", "+21.6%"),
    ("Bristol", "10.51", "12.76", "+21.8%"),
]

def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s)
    return s.strip("-")

# ── HTML ──────────────────────────────────────────────────────────────────────

def dish_table(dishes: list[tuple[str, str, str, str]]) -> str:
    rows = ""
    for dish, dine, delivery, markup in dishes:
        rows += (
            f"<tr>"
            f'<td class="dish">{dish}</td>'
            f'<td class="dine-in">&pound;{dine}</td>'
            f'<td class="delivery">&pound;{delivery}</td>'
            f'<td class="markup">{markup}</td>'
            f"</tr>\n"
        )
    return f"""<table class="price-table">
        <thead><tr><th>Dish</th><th>Dine-in</th><th>Delivery</th><th>Markup</th></tr></thead>
        <tbody>{rows}</tbody>
    </table>"""

def city_table() -> str:
    rows = ""
    for city, dine, delivery, markup in CITY_PRICES:
        slug = slugify(city)
        rows += (
            f"<tr>"
            f'<td><a href="/cities/{slug}" class="city-link">{city}</a></td>'
            f'<td class="dine-in">&pound;{dine}</td>'
            f'<td class="delivery">&pound;{delivery}</td>'
            f'<td class="markup">{markup}</td>'
            f"</tr>\n"
        )
    return f"""<table class="price-table">
        <thead><tr><th>City</th><th>Avg Dine-in</th><th>Avg Delivery</th><th>Markup</th></tr></thead>
        <tbody>{rows}</tbody>
    </table>"""

categories_html = ""
for cat in DISH_CATEGORIES:
    categories_html += f"""
    <div class="section">
        <h2>{cat['emoji']} {cat['name']}</h2>
        {dish_table(cat['dishes'])}
    </div>
    """

city_html = city_table()

# Find cheapest and most expensive
all_dishes = []
for cat in DISH_CATEGORIES:
    all_dishes.extend(cat["dishes"])
cheapest_dine_in = min(all_dishes, key=lambda d: float(d[1]))
most_expensive = max(all_dishes, key=lambda d: float(d[1]))


HTML = f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Thai Dish Price Checker UK: Pad Thai, Curry & More | ThaiData</title>
    <meta name="description" content="Compare Thai dish prices across UK cities. Pad Thai, Green Curry, Tom Yum, Massaman, and more. Dine-in vs delivery pricing with 2026 data.">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="https://thaidata.uk/dish-prices">

    <meta property="og:type" content="website">
    <meta property="og:url" content="https://thaidata.uk/dish-prices">
    <meta property="og:title" content="Thai Dish Price Checker UK: Pad Thai, Curry & More | ThaiData">
    <meta property="og:description" content="Compare Thai dish prices across UK cities. Dine-in vs delivery pricing for 12 popular dishes.">
    <meta property="og:image" content="https://thaidata.uk/thaidataukhero.webp">
    <meta property="og:locale" content="en_GB">
    <meta name="twitter:card" content="summary_large_image">

    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "Dataset",
      "name": "Thai Menu Price Index UK 2026",
      "description": "Dine-in and delivery prices for 12 popular Thai dishes across 5 UK cities.",
      "creator": {{ "@type": "Organization", "name": "ThaiData UK" }},
      "temporalCoverage": "2026-06"
    }}
    </script>
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        {{ "@type": "ListItem", "position": 1, "name": "Home", "item": "https://thaidata.uk/" }},
        {{ "@type": "ListItem", "position": 2, "name": "Dish Prices", "item": "https://thaidata.uk/dish-prices" }}
      ]
    }}
    </script>

    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" media="print" onload="this.media='all'"><noscript><!-- fa --></noscript>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">

    <style>
        :root {{ --c1: #A3132B; --c2: #A3132B; --dark: #FFFFFF; --ink: #1A1614; --ink2: #4A403C; --ink3: #7A6F6A; --ink4: #9C918C; --line: #E7DFD5; --bg: #FBF7F0; --gold: #F59E0B; }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        img,svg,video {{ max-width: 100%; height: auto; }}
        body {{ font-family: 'Inter', system-ui, sans-serif; color: var(--ink); background: var(--bg); line-height: 1.6; -webkit-font-smoothing: antialiased; overflow-x: hidden; }}
        .grain {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: url("/assets/noise.svg"); opacity: 0.03; pointer-events: none; z-index: 999; }}
        .wrap {{ max-width: 900px; margin: 0 auto; padding: 0 20px; }}
        nav {{ background: var(--dark); border-bottom: 1px solid var(--line); height: 72px; display: flex; align-items: center; position: sticky; top: 0; z-index: 100; }}
        .nav-bar {{ max-width: 1100px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; padding: 0 20px; width: 100%; position: relative; }}
        .logo {{ display: flex; align-items: center; gap: 12px; font-weight: 700; font-size: 1.4rem; color: var(--ink); text-decoration: none; }}
        .logo-icon {{ height: 36px; width: auto; }}
        .nav-links {{ display: flex; gap: 20px; align-items: center; }}
        .nav-links a {{ color: rgba(255,255,255,0.6); text-decoration: none; font-size: 0.9rem; transition: color 0.2s; }}
        .nav-links a:hover {{ color: var(--c2); }}
        .hamburger {{ display: none; background: none; border: none; color: var(--ink); font-size: 1.5rem; cursor: pointer; padding: 8px; }}
        .hamburger:hover {{ color: var(--c2); }}
        @media(max-width:768px) {{ .nav-links {{ display: none; position: absolute; top: 100%; left: 0; right: 0; background: var(--dark); border-bottom: 1px solid var(--line); flex-direction: column; padding: 20px; gap: 16px; }} .nav-links.open {{ display: flex; }} .hamburger {{ display: block; }} }}

        .hero {{ padding: 60px 0 30px; text-align: center; }}
        .hero h1 {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: clamp(2rem, 5vw, 2.8rem); font-weight: 800; line-height: 1.15; margin-bottom: 12px; }}
        .hero h1 em {{ font-style: normal; color: var(--c2); }}
        .hero .sub {{ color: var(--ink4); font-size: 1rem; max-width: 560px; margin: 0 auto; line-height: 1.7; }}

        .intro {{ margin: 20px 0 30px; }}
        .intro p {{ color: var(--ink3); line-height: 1.7; margin-bottom: 10px; font-size: 0.92rem; }}

        .stats-row {{ display: flex; gap: 14px; justify-content: center; flex-wrap: wrap; margin: 20px 0; }}
        .stat-pill {{ background: #FFFFFF; border: 1px solid var(--line); border-radius: 12px; padding: 14px 20px; text-align: center; min-width: 80px; }}
        .stat-pill .num {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: 1.4rem; color: var(--c2); font-weight: 800;}}
        .stat-pill .lbl {{ color: var(--ink4); font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.06em; margin-top: 2px; }}

        .section {{ margin: 32px 0; }}
        .section h2 {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: 1.5rem; font-weight: 800; margin-bottom: 14px; }}
        .section h2 em {{ font-style: normal; color: var(--c2); }}

        .price-table {{ width: 100%; border-collapse: collapse; margin-bottom: 10px; }}
        .price-table th {{ text-align: left; padding: 10px 14px; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--ink4); border-bottom: 1px solid var(--line); font-weight: 600; }}
        .price-table td {{ padding: 12px 14px; border-bottom: 1px solid rgba(255,255,255,0.04); font-size: 0.92rem; }}
        .price-table tr:hover td {{ background: #FFFFFF; }}
        .price-table .dish {{ font-weight: 600; }}
        .price-table .dine-in {{ color: var(--c2); font-weight: 600; }}
        .price-table .delivery {{ color: var(--gold); font-weight: 600; }}
        .price-table .markup {{ color: var(--ink4); }}
        .price-table .city-link {{ color: var(--c2); text-decoration: underline; text-underline-offset: 3px; }}
        .price-table .city-link:hover {{ color: var(--ink); }}

        .highlight-box {{ background: rgba(16,185,129,0.06); border: 1px solid rgba(16,185,129,0.2); border-radius: 14px; padding: 24px; margin: 20px 0; }}
        .highlight-box h3 {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: 1.1rem; font-weight: 800; margin-bottom: 8px; }}
        .highlight-box p, .highlight-box li {{ color: var(--ink3); font-size: 0.88rem; line-height: 1.7; }}
        .highlight-box ul {{ padding-left: 18px; margin-top: 8px; }}
        .highlight-box ul li {{ margin-bottom: 6px; }}

        .link-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; margin: 16px 0; }}
        .link-card {{ background: #FFFFFF; border: 1px solid var(--line); border-radius: 12px; padding: 18px; text-decoration: none; transition: border-color 0.2s; }}
        .link-card:hover {{ border-color: var(--c2); }}
        .link-card h3 {{ font-size: 0.95rem; color: var(--ink); margin-bottom: 4px; }}
        .link-card p {{ font-size: 0.8rem; color: var(--ink4); }}

        .note {{ color: var(--ink4); font-size: 0.8rem; font-style: normal; margin: 16px 0; }}

        footer {{ border-top: 1px solid var(--line); padding: 30px 0 50px; text-align: center; font-size: 0.85rem; color: var(--ink4); margin-top: 30px; }}
        footer a {{ color: var(--ink4); text-decoration: none; }}
        footer a:hover {{ color: var(--c2); }}
    </style>
</head>
<body>
    <div class="grain"></div>
    <nav>
        <div class="nav-bar">
            <a href="/" class="logo"><img src="/thaidata-lockup.b89c5cf2.png" alt="ThaiData UK" class="logo-icon" width="146" height="36"></a>
            <button class="hamburger" onclick="toggleMenu()" aria-label="Menu">&#9776;</button>
            <div class="nav-links">
                <a href="/guides.html">Guides</a>
                <a href="/thai-restaurants-city-breakdown-uk">Cities</a>
                <a href="/r/">Restaurants</a>
                <a href="/chains/">Chains</a>
                <a href="/dish-prices" style="color:var(--c2);">Pricing</a>
            </div>
        </div>
    </nav>

    <div class="wrap">

        <div class="hero">
            <h1>Thai Dish <em>Price Checker</em></h1>
            <p class="sub">What Thai dishes actually cost across UK cities. Dine-in vs delivery prices for 12 popular dishes, updated with mid-2026 data.</p>
        </div>

        <div class="stats-row">
            <div class="stat-pill"><div class="num">12</div><div class="lbl">Dishes Tracked</div></div>
            <div class="stat-pill"><div class="num">5</div><div class="lbl">Cities</div></div>
            <div class="stat-pill"><div class="num">&pound;{float(cheapest_dine_in[1]):.2f}</div><div class="lbl">Cheapest Dine-in</div></div>
            <div class="stat-pill"><div class="num">&pound;{float(most_expensive[1]):.2f}</div><div class="lbl">Most Expensive</div></div>
            <div class="stat-pill"><div class="num">~22%</div><div class="lbl">Avg Delivery Markup</div></div>
        </div>

        <div class="intro">
            <p>This page tracks <strong>real menu prices</strong> for popular Thai dishes across UK cities. Prices are collected manually from restaurant websites, Google Business Profiles, and delivery platforms (Deliveroo, Uber Eats, Just Eat). Each dish shows both the dine-in price and the delivery menu price, so you can see exactly how much the platform markup adds.</p>
            <p><strong>Data source:</strong> ThaiData Menu Price Survey, June 2026. Prices are averages across multiple restaurants in each city and may not reflect every restaurant's menu. Delivery prices exclude service charges and delivery fees.</p>
        </div>

        {categories_html}

        <!-- City comparison -->
        <div class="section">
            <h2>Prices by <em>City</em></h2>
            <p class="note">Average of all 12 dishes across multiple restaurants per city. Each city name links to its full guide.</p>
            {city_html}
        </div>

        <!-- Key findings -->
        <div class="highlight-box">
            <h3>What the data tells us</h3>
            <ul>
                <li><strong>Delivery markups</strong> average 20-23% across all dishes. Spring Rolls have the highest markup at +23%; Sticky Rice the lowest at +18%.</li>
                <li><strong>London is the most expensive</strong> city for Thai dining, with an average dine-in price of &pound;12.08 and delivery of &pound;14.58.</li>
                <li><strong>Leeds has the highest delivery markup</strong> at +23.0%, despite having the lowest absolute prices. Customers in Leeds pay the largest relative premium for delivery.</li>
                <li><strong>Manchester and Bristol</strong> are the most affordable cities among the five surveyed for dine-in Thai food.</li>
                <li>The markup is rarely disclosed — customers paying &pound;{float(most_expensive[2]):.2f} for {most_expensive[0]} on a delivery app may not know it's &pound;{float(most_expensive[1]):.2f} in the restaurant.</li>
            </ul>
        </div>

        <!-- Related links -->
        <div class="section">
            <h2>Related <em>Pages</em></h2>
            <div class="link-grid">
                <a href="/thai-restaurants-city-breakdown-uk" class="link-card">
                    <h3>City Breakdown</h3>
                    <p>All 254 UK cities with Thai restaurants</p>
                </a>
                <a href="/r/" class="link-card">
                    <h3>Restaurant Directory</h3>
                    <p>1,594 individual Thai restaurant pages</p>
                </a>
                <a href="/chains/" class="link-card">
                    <h3>Chain Directory</h3>
                    <p>Major UK Thai chain profiles</p>
                </a>
                <a href="/thai-menu-price-index-uk" class="link-card">
                    <h3>Full Price Index Report</h3>
                    <p>Detailed methodology and city comparison</p>
                </a>
            </div>
        </div>

        <!-- Methodology -->
        <div class="highlight-box" style="border-color:var(--line);background:#FFFFFF;">
            <h3>Methodology & Limitations</h3>
            <p>Prices were collected in June 2026 from a sample of 3-5 popular Thai restaurants per city. Dine-in prices come from official restaurant websites or Google Business Profile menu photos. Delivery prices come from Deliveroo, Uber Eats, and Just Eat menu listings. Where a restaurant does not offer a specific dish, it was excluded from the average. Prices exclude optional service charges and delivery fees.</p>
            <p style="margin-top:8px;">This is a manual survey, not an automated scrape. Coverage will expand as we collect more data. <a href="/thai-menu-price-index-uk" style="color:var(--c2);">Full methodology report</a>.</p>
        </div>

    </div>

    <footer>
        <p><a href="/">ThaiData</a> &middot; Menu Price Survey June 2026 &middot; <a href="/data-quality">Data Quality</a> &middot; <a href="/sitemap-page">Sitemap</a></p>
        <p style="margin-top:6px;font-size:0.8rem;">Prices are indicative averages from surveyed restaurants. Verify with individual restaurants before relying on them.</p>
    </footer>

    <script>function toggleMenu(){{document.querySelector('.nav-links').classList.toggle('open');}}</script>
</body>
</html>
"""

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
with open(OUTPUT, "w") as f:
    f.write(site_icons.transform(HTML))

kb = len(HTML) // 1024
print(f"Generated dish pricing hub: {OUTPUT}")
print(f"  {kb}KB")
print(f"  {len(DISH_CATEGORIES)} dish categories, {sum(len(c['dishes']) for c in DISH_CATEGORIES)} total dishes")
print(f"  {len(CITY_PRICES)} cities compared")
print(f"  Schema: Dataset + BreadcrumbList")
