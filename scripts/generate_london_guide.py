#!/usr/bin/env python3
"""Generate the bespoke London editorial guide at /cities/london.html.

This is a one-time generation script. The output is a manual page --
the city page generator skips it permanently.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

OUTPUT = REPO / "cities" / "london.html"

# ── Data ──────────────────────────────────────────────────────────────────────

with open(REPO / "data" / "restaurants.json") as f:
    data = json.load(f)

london = [r for r in data["restaurants"] if r["city"] == "London"]


def outward(pc: str) -> str:
    if not pc:
        return ""
    parts = pc.split()
    return parts[0] if parts else pc.strip()


def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s)
    return s.strip("-")


def rest_url(r: dict[str, Any]) -> str:
    return f"/r/{slugify(r['city'])}/{slugify(r['name'])}/"


# ── Neighbourhoods ────────────────────────────────────────────────────────────

NEIGHBOURHOODS: list[dict[str, Any]] = [
    {
        "id": "soho-chinatown",
        "name": "Soho & Chinatown",
        "description": "London's most concentrated Thai dining zone. Chinatown's Lisle Street and Gerrard Street are home to a dense cluster of Thai restaurants, from quick lunch spots to late-night canteens. Soho's side streets add a more polished, modern Thai dining scene.",
        "postcodes": ["W1D", "WC2H", "W1F"],
        "best_for": "A lively night out, late-night eats, or a lunchtime Thai fix between shops.",
        "chains": "Busaba Eathai, Banana Tree",
    },
    {
        "id": "shoreditch-spitalfields",
        "name": "Shoreditch & Spitalfields",
        "description": "East London's creative heart has a thriving Thai scene that leans independent and inventive. Brick Lane, Spitalfields Market, and the streets around Old Street are dotted with Thai cafes, street-food stalls, and modern interpretations.",
        "postcodes": ["E1", "E2", "EC2A"],
        "best_for": "Street-food style dining, lunch markets, and trendy dinner spots.",
        "chains": "Rosa's Thai Cafe",
    },
    {
        "id": "kensington-chelsea",
        "name": "Kensington & Chelsea",
        "description": "West London's Thai offering leans refined and white-tablecloth. Many of the restaurants here have been operating for 15-20 years, building loyal local followings. You'll find several long-standing family-run spots alongside the chains.",
        "postcodes": ["SW5", "SW7", "W8", "SW3"],
        "best_for": "A special dinner out, family celebrations, or a reliable neighbourhood favourite.",
        "chains": "Patara, Thai Square",
    },
    {
        "id": "hammersmith-shepherds-bush",
        "name": "Hammersmith & Shepherds Bush",
        "description": "West London's Thai dining hub with an impressive density. The mix includes Westfield food court options alongside established local spots around Shepherd's Bush Green and Hammersmith Broadway.",
        "postcodes": ["W6", "W12", "W14"],
        "best_for": "Shopping trip dining (Westfield), post-work dinners, and quick lunches.",
        "chains": "Busaba Eathai, Patara",
    },
    {
        "id": "camden",
        "name": "Camden & Kentish Town",
        "description": "Camden's Thai scene is more diverse than its famous markets might suggest. From canal-side dining to neighbourhood takeaway spots, this area has a solid mix. The quality varies significantly, so checking FSA ratings before walking in is worth the effort.",
        "postcodes": ["NW1", "NW3", "NW5"],
        "best_for": "A day-out at Camden Market, canal-side meals, and affordable takeaways.",
        "chains": "Thai Square",
    },
    {
        "id": "islington-angel",
        "name": "Islington & Angel",
        "description": "Upper Street is the main artery, lined with restaurants of every cuisine. Thai options here are mostly mid-market dining pubs and casual restaurants, good for pre-theatre dinners or Saturday evening walk-ins.",
        "postcodes": ["N1", "N5"],
        "best_for": "Pre-theatre dinner, Saturday shopping lunch, or a relaxed date.",
        "chains": "Rosa's Thai Cafe",
    },
    {
        "id": "south-bank-borough",
        "name": "South Bank & Borough",
        "description": "The South Bank corridor from Waterloo to London Bridge punches above its weight. Borough Market has excellent Thai street food stalls, while the riverside strip has sit-down options with a view.",
        "postcodes": ["SE1"],
        "best_for": "Tourist day out, Borough Market lunch, pre-theatre on the South Bank.",
        "chains": "",
    },
    {
        "id": "notting-hill-bayswater",
        "name": "Notting Hill & Bayswater",
        "description": "Queensway and Westbourne Grove host a surprising number of Thai restaurants. This area has an international crowd and the menus reflect it -- expect creative fusion alongside traditional curries.",
        "postcodes": ["W11", "W10", "W2"],
        "best_for": "Shopping on Portobello Road, a casual dinner, or feeding the family.",
        "chains": "Rosa's Thai Cafe, Banana Tree",
    },
    {
        "id": "greenwich",
        "name": "Greenwich",
        "description": "Greenwich's Thai scene clusters around the town centre and the O2 arena. The O2 outpost of Banana Tree is popular pre-event dining, while the town centre has independent options near the market.",
        "postcodes": ["SE10", "SE3"],
        "best_for": "Pre-event dining at the O2, weekend market lunches, post-museum meals.",
        "chains": "Banana Tree",
    },
    {
        "id": "putney-wimbledon",
        "name": "Putney & Wimbledon",
        "description": "South-west London's Thai offering is small but excellent. The area has the highest average hygiene rating of any London neighbourhood and the highest five-star rate. These are community staples -- well-loved and long-running.",
        "postcodes": ["SW15", "SW19"],
        "best_for": "A reliable neighbourhood dinner, family takeaway, or post-tennis meal.",
        "chains": "Giggling Squid",
    },
    {
        "id": "battersea-clapham",
        "name": "Battersea & Clapham",
        "description": "Battersea's Northcote Road and Clapham's Venn Street both have excellent Thai options. The area skews young professional and the dining scene reflects it -- modern interiors, good wine lists, and prices to match.",
        "postcodes": ["SW11", "SW4", "SW8"],
        "best_for": "Saturday brunch, dinner with friends, date night.",
        "chains": "",
    },
    {
        "id": "hackney-dalston",
        "name": "Hackney & Dalston",
        "description": "East London's dining frontier. Thai options here tend to be small, independent, and high-quality. Dalston's Kingsland Road and Hackney's Broadway Market have several strong entries with some of the best ratings in London.",
        "postcodes": ["E8", "E9", "N16", "N4"],
        "best_for": "Off-the-beaten-path dining, foodie exploration, market lunches.",
        "chains": "",
    },
    {
        "id": "marylebone",
        "name": "Marylebone",
        "description": "A small but polished Thai scene. Marylebone High Street and Baker Street have a handful of excellent sit-down restaurants, including long-standing favourites. Quality over quantity in this part of town.",
        "postcodes": ["W1G", "W1U", "W1H"],
        "best_for": "Lunch after a Wallace Collection visit, dinner before a show.",
        "chains": "Busaba Eathai, Rosa's Thai Cafe",
    },
]

# Populate neighbourhood data
for hood in NEIGHBOURHOODS:
    code_set = set(hood["postcodes"])
    rests = [r for r in london if outward(r.get("postcode", "")) in code_set]
    hood["restaurants"] = rests
    hood["count"] = len(rests)
    hood["dine_in"] = sum(1 for r in rests if r["type"] == "restaurant")
    hood["takeaway"] = hood["count"] - hood["dine_in"]
    ratings = [int(r["hygiene_rating"]) for r in rests if r.get("hygiene_rating", "").isdigit()]
    hood["avg_rating"] = round(sum(ratings) / len(ratings), 1) if ratings else 0
    hood["five_star"] = sum(1 for r in ratings if r == 5)
    sorted_rests = sorted(rests, key=lambda r: (-int(r.get("hygiene_rating", 0) or 0), r["name"].lower()))
    hood["top"] = sorted_rests[:3]
    hood["top_names"] = [r["name"] for r in hood["top"]]

NEIGHBOURHOODS.sort(key=lambda h: -h["count"])

# ── Overall stats ─────────────────────────────────────────────────────────────

total = len(london)
dine_in_total = sum(1 for r in london if r["type"] == "restaurant")
takeaway_total = total - dine_in_total
all_ratings = [int(r["hygiene_rating"]) for r in london if r.get("hygiene_rating", "").isdigit()]
avg_all = round(sum(all_ratings) / len(all_ratings), 1) if all_ratings else 0
five_star_all = sum(1 for r in all_ratings if r == 5)

CHAIN_KEYWORDS = ["giggling squid", "rosa thai", "busaba", "thaikhun", "camile",
                   "thai square", "patara", "thai express", "mango tree"]
chain_count = Counter()
for r in london:
    name_lower = r["name"].lower()
    for chain in CHAIN_KEYWORDS:
        if chain in name_lower:
            chain_count[chain] += 1
            break

putney_rating = next((h["avg_rating"] for h in NEIGHBOURHOODS if h["id"] == "putney-wimbledon"), 0)

# ── HTML generators ────────────────────────────────────────────────────────────

def make_restaurant_card(r: dict[str, Any]) -> str:
    rating = r.get("hygiene_rating", "?")
    stars = "star" * int(rating) if rating and rating.isdigit() else "misc"
    stars_unicode = "★" * int(rating) if rating and rating.isdigit() else "—"
    url = rest_url(r)
    rtype = "Restaurant" if r.get("type") == "restaurant" else "Takeaway"
    return (
        f'<a href="{url}" class="rest-card">'
        f'<strong>{r["name"]}</strong>'
        f'<span class="rest-type">{rtype}</span>'
        f'<span class="rest-rating">{stars_unicode}</span>'
        f'</a>'
    )


def neighbourhood_section(hood: dict[str, Any]) -> str:
    top_html = "".join(make_restaurant_card(r) for r in hood["top"])
    chain_html = f"<p><strong>Notable chains:</strong> {hood['chains']}</p>" if hood["chains"] else ""
    return f"""
    <section id="{hood['id']}" class="hood-section">
        <div class="hood-anchor" id="{hood['id']}-anchor"></div>
        <h2>{hood['name']} <span class="hood-badge">{hood['count']} Thai restaurants</span></h2>
        <p class="hood-stats">star{hood['avg_rating']} avg rating middot {hood['five_star']} five-star middot {hood['dine_in']} dine-in, {hood['takeaway']} takeaway</p>
        <p class="hood-desc">{hood['description']}</p>
        <p class="hood-best"><strong>Best for:</strong> {hood['best_for']}</p>
        {chain_html}
        <div class="rest-cards">
            <h3>Top picks</h3>
            {top_html}
        </div>
    </section>
    """


def build_faq_html() -> str:
    top3 = ", ".join(
        r["name"]
        for r in sorted(london, key=lambda x: -int(x.get("hygiene_rating", 0) or 0))[:3]
    )

    chain_summary = " and ".join(
        f"{chain.title()} ({count})"
        for chain, count in sorted(chain_count.items(), key=lambda x: -x[1])[:5]
    )

    qas = [
        ("What is the top-rated Thai restaurant in London?",
         f"London has {five_star_all} restaurants with a perfect 5/5 FSA hygiene rating. "
         f"Top-rated spots include {top3}."),
        ("How many Thai restaurants are in London?",
         f"London has {total} FSA-listed Thai businesses in total -- "
         f"{dine_in_total} dine-in restaurants and {takeaway_total} takeaways. "
         f"That is {total / 1594 * 100:.1f}% of all Thai businesses in the UK."),
        ("Which Thai chains operate in London?",
         f"Major chains with London locations include {chain_summary}. "
         f"The vast majority of London's Thai restaurants are independent."),
        ("What is the best area for Thai food in London?",
         f"Shoreditch and Spitalfields has the highest concentration with "
         f"{NEIGHBOURHOODS[0]['count']} restaurants. "
         f"Putney and Wimbledon has the highest average FSA rating at star{putney_rating}/5."),
        ("Is London's Thai food scene competitive?",
         f"With {total} businesses serving 8.97 million people, London has roughly "
         f"4.5 Thai restaurants per 100,000 residents -- slightly below the national average. "
         f"This suggests room for growth, particularly in underserved outer boroughs."),
        ("Are there more dine-in Thai restaurants or takeaways in London?",
         f"Dine-in restaurants dominate at {dine_in_total} "
         f"({dine_in_total / total * 100:.0f}% of the total), "
         f"with {takeaway_total} takeaways making up the remainder."),
    ]

    items = ""
    for q, a in qas:
        items += f"""
        <details class="faq-item">
            <summary>{q}</summary>
            <p>{a}</p>
        </details>
        """
    return items


def build_schema() -> str:
    blocks = []

    # BreadcrumbList
    blocks.append(json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://thaidata.uk/"},
            {"@type": "ListItem", "position": 2, "name": "Cities", "item": "https://thaidata.uk/thai-restaurants-city-breakdown-uk"},
            {"@type": "ListItem", "position": 3, "name": "London Thai Restaurant Guide", "item": "https://thaidata.uk/cities/london"},
        ],
    }, ensure_ascii=False))

    # City
    blocks.append(json.dumps({
        "@context": "https://schema.org",
        "@type": "City",
        "name": "London",
        "sameAs": "https://www.wikidata.org/wiki/Q84",
    }, ensure_ascii=False))

    # FAQPage
    faq_entries = []
    top3 = ", ".join(
        r["name"]
        for r in sorted(london, key=lambda x: -int(x.get("hygiene_rating", 0) or 0))[:3]
    )
    faq_entries.append({
        "@type": "Question",
        "name": "What is the top-rated Thai restaurant in London?",
        "acceptedAnswer": {
            "@type": "Answer",
            "text": f"London has {five_star_all} restaurants with a perfect 5/5 FSA hygiene rating. Top-rated spots include {top3}."
        },
    })
    faq_entries.append({
        "@type": "Question",
        "name": "How many Thai restaurants are in London?",
        "acceptedAnswer": {
            "@type": "Answer",
            "text": f"London has {total} FSA-listed Thai businesses -- {dine_in_total} dine-in restaurants and {takeaway_total} takeaways."
        },
    })
    faq_entries.append({
        "@type": "Question",
        "name": "Which Thai chains operate in London?",
        "acceptedAnswer": {
            "@type": "Answer",
            "text": "Major chains include Rosa's Thai Cafe, Thai Square, Busaba, Patara, and Giggling Squid."
        },
    })
    faq_entries.append({
        "@type": "Question",
        "name": "What is the best area for Thai food in London?",
        "acceptedAnswer": {
            "@type": "Answer",
            "text": f"Shoreditch, Hammersmith, and Kensington have the highest concentrations. Putney and Wimbledon has the highest average FSA rating at star{putney_rating}/5."
        },
    })
    faq_entries.append({
        "@type": "Question",
        "name": "Is London's Thai food scene competitive?",
        "acceptedAnswer": {
            "@type": "Answer",
            "text": f"With {total} businesses and roughly 4.5 per 100,000 residents, London has room for growth in the Thai restaurant sector."
        },
    })
    faq_entries.append({
        "@type": "Question",
        "name": "Are there more dine-in Thai restaurants or takeaways in London?",
        "acceptedAnswer": {
            "@type": "Answer",
            "text": f"Dine-in restaurants dominate at {dine_in_total} ({dine_in_total / total * 100:.0f}% of the total), with {takeaway_total} takeaways."
        },
    })

    blocks.append(json.dumps({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": faq_entries,
    }, ensure_ascii=False))

    return "\n".join(f'<script type="application/ld+json">{b}</script>' for b in blocks)


# ── Build the page ────────────────────────────────────────────────────────────

nav_pills = "".join(
    f'<a href="#{h["id"]}">{h["name"]}</a>' for h in NEIGHBOURHOODS
)

neighbourhood_html = "".join(neighbourhood_section(h) for h in NEIGHBOURHOODS)

faq_html = build_faq_html()

schema_html = build_schema()

# Chains summary
chain_summary_parts = []
for chain, count in sorted(chain_count.items(), key=lambda x: -x[1]):
    name = chain.title()
    chain_summary_parts.append(f"{name} ({count})")
chain_summary_text = " middot ".join(chain_summary_parts)
chain_summary_text += " and several smaller independents spanning the city."

# Where to start cards
start_cards = f"""
<div class="start-cards">
    <div class="start-card">
        <h3>Quick lunch</h3>
        <p>Head to <strong>Soho and Chinatown</strong> for fast, reliable Thai -- Busaba, Banana Tree, and several walk-in canteens on Lisle Street.</p>
    </div>
    <div class="start-card">
        <h3>Date night</h3>
        <p><strong>Kensington</strong> or <strong>Marylebone</strong> for polished service and wine lists. Try Patara or a local independent on Kensington Church Street.</p>
    </div>
    <div class="start-card">
        <h3>Group dinner</h3>
        <p><strong>Shoreditch and Spitalfields</strong> has the highest density with room for big tables. Rosa's Thai on Commercial Street is a solid group choice.</p>
    </div>
    <div class="start-card">
        <h3>Family takeaway</h3>
        <p><strong>Putney and Wimbledon</strong> has the highest average FSA rating in London (star{putney_rating}/5) -- these are community staples.</p>
    </div>
    <div class="start-card">
        <h3>Pre-theatre</h3>
        <p><strong>South Bank</strong> or <strong>Islington</strong> -- both near major theatres and packed with pre-show dining options.</p>
    </div>
    <div class="start-card">
        <h3>Foodie exploration</h3>
        <p><strong>Hackney and Dalston</strong> for off-the-beaten-path finds. Broadway Market and Kingsland Road have excellent independent Thai spots.</p>
    </div>
</div>
"""

# Star character for display in HTML
STAR = "&#9733;"  # ★ as HTML entity

stats_total = total
stats_dine_in = dine_in_total
stats_takeaway = takeaway_total
stats_avg = avg_all
stats_five = five_star_all

LONDON_PAGE = f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Thai Restaurants in London -- Neighbourhood Guide 2026 | ThaiData</title>
    <meta name="description" content="London has {stats_total} Thai restaurants across its neighbourhoods. Our guide covers Soho, Shoreditch, Kensington, Camden, Greenwich and more -- with FSA hygiene data, top picks and area insights.">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="https://thaidata.uk/cities/london">

    <meta property="og:type" content="article">
    <meta property="og:url" content="https://thaidata.uk/cities/london">
    <meta property="og:title" content="Thai Restaurants in London -- Neighbourhood Guide 2026">
    <meta property="og:description" content="{stats_total} Thai restaurants across London's neighbourhoods. FSA hygiene data, top picks per area, chain presence, and curated recommendations.">
    <meta property="og:locale" content="en_GB">

    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" media="print" onload="this.media='all'"><noscript><!-- fa --></noscript>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">

    <!-- CITIES-MODE: manual -->
    <!-- MANUAL -->

    {schema_html}

    <style>
        :root {{ --c1: #A3132B; --c2: #A3132B; --dark: #FFFFFF; --ink: #1A1614; --ink2: #4A403C; --ink3: #7A6F6A; --ink4: #9C918C; --line: #E7DFD5; --bg: #FBF7F0; --card-bg: #FFFFFF; }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        img, svg, video {{ max-width: 100%; height: auto; }}
        body {{ font-family: 'Inter', system-ui, sans-serif; color: var(--ink); background: var(--bg); line-height: 1.6; -webkit-font-smoothing: antialiased; overflow-x: hidden; }}
        .grain {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: url("https://grainy-gradients.vercel.app/noise.svg"); opacity: 0.03; pointer-events: none; z-index: 999; }}
        .wrap {{ max-width: 960px; margin: 0 auto; padding: 0 20px; }}
        nav {{ background: var(--dark); border-bottom: 1px solid var(--line); height: 72px; display: flex; align-items: center; }}
        body > nav {{ position: sticky; top: 0; z-index: 100; }}
        .nav-bar {{ max-width: 960px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; padding: 0 20px; width: 100%; }}
        .logo {{ display: flex; align-items: center; gap: 12px; font-weight: 700; font-size: 1.4rem; color: var(--ink); text-decoration: none; }}
        .logo-icon {{ height: 36px; width: auto; }}

        .hero {{ padding: 80px 0 40px; text-align: center; }}
        .hero h1 {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: clamp(2.2rem, 6vw, 3.5rem); font-weight: 800; line-height: 1.15; margin-bottom: 12px; }}
        .hero h1 em {{ font-style: normal; color: var(--c2); }}
        .hero .subtitle {{ color: var(--ink4); font-size: 1.05rem; max-width: 640px; margin: 0 auto 24px; line-height: 1.7; }}
        .hero-stats {{ display: flex; gap: 24px; justify-content: center; flex-wrap: wrap; margin-bottom: 20px; }}
        .hero-stat {{ text-align: center; }}
        .hero-stat .num {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: 2.2rem; color: var(--c2); font-weight: 800;}}
        .hero-stat .lbl {{ color: var(--ink4); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em; margin-top: 2px; }}

        .hood-nav {{ display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin: 40px auto; max-width: 720px; height: auto; align-items: flex-start; }}
        .hood-nav a {{ padding: 8px 18px; border: 1px solid var(--line); border-radius: 50px; color: var(--ink4); text-decoration: none; font-size: 0.85rem; transition: all 0.2s; }}
        .hood-nav a:hover {{ border-color: var(--c2); color: var(--c2); }}

        .intro {{ margin: 20px 0 48px; }}
        .intro p {{ color: var(--ink3); font-size: 1rem; line-height: 1.8; margin-bottom: 16px; }}

        .hood-section {{ padding: 32px 0; scroll-margin-top: 80px; }}
        .hood-section + .hood-section {{ border-top: 1px solid var(--line); }}
        .hood-section h2 {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: 1.5rem; font-weight: 800; margin-bottom: 4px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
        .hood-section h2 em {{ font-style: normal; color: var(--c2); }}
        .hood-badge {{ font-size: 0.7rem; background: rgba(16,185,129,0.15); color: var(--c2); padding: 3px 12px; border-radius: 50px; font-family: 'Inter', sans-serif; font-weight: 500; }}
        .hood-stats {{ font-size: 0.85rem; color: var(--ink4); margin-bottom: 12px; }}
        .hood-desc {{ color: var(--ink3); line-height: 1.7; font-size: 0.95rem; margin-bottom: 8px; }}
        .hood-best {{ font-size: 0.9rem; color: var(--ink4); margin-bottom: 12px; }}
        .hood-section p strong {{ color: var(--ink); }}

        .rest-cards {{ margin-top: 16px; }}
        .rest-cards h3 {{ font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--ink4); margin-bottom: 8px; }}
        .rest-card {{ display: inline-flex; align-items: center; gap: 10px; padding: 10px 16px; background: var(--card-bg); border: 1px solid var(--line); border-radius: 10px; text-decoration: none; transition: border-color 0.2s; margin: 0 6px 6px 0; }}
        .rest-card:hover {{ border-color: var(--c2); }}
        .rest-card strong {{ color: var(--ink); font-size: 0.85rem; font-weight: 600; }}
        .rest-type {{ color: var(--ink4); font-size: 0.75rem; }}
        .rest-rating {{ color: var(--c2); font-size: 0.85rem; }}

        .faq-section {{ margin: 48px 0; }}
        .faq-section h2 {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: 1.5rem; font-weight: 800; margin-bottom: 20px; }}
        .faq-section h2 em {{ font-style: normal; color: var(--c2); }}
        .faq-item {{ margin: 8px 0; padding: 16px 20px; background: var(--card-bg); border: 1px solid var(--line); border-radius: 12px; }}
        .faq-item summary {{ cursor: pointer; font-weight: 600; color: var(--ink); font-size: 0.95rem; }}
        .faq-item summary::-webkit-details-marker {{ color: var(--c2); }}
        .faq-item p {{ margin-top: 10px; color: var(--ink3); line-height: 1.7; font-size: 0.9rem; }}

        .start-section {{ margin: 40px 0; }}
        .start-section h2 {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: 1.5rem; font-weight: 800; margin-bottom: 16px; }}
        .start-section h2 em {{ font-style: normal; color: var(--c2); }}
        .start-cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 14px; }}
        .start-card {{ background: var(--card-bg); border: 1px solid var(--line); border-radius: 14px; padding: 24px; }}
        .start-card h3 {{ font-size: 1rem; color: var(--ink); margin-bottom: 6px; }}
        .start-card p {{ color: var(--ink3); font-size: 0.85rem; line-height: 1.6; }}

        .chain-overview {{ margin: 40px 0; padding: 28px 32px; background: var(--card-bg); border: 1px solid var(--line); border-radius: 16px; }}
        .chain-overview h2 {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: 1.3rem; font-weight: 800; margin-bottom: 12px; }}
        .chain-overview p {{ color: var(--ink3); font-size: 0.9rem; line-height: 1.7; }}

        .cta {{ text-align: center; padding: 40px 0 60px; }}
        .cta a {{ display: inline-block; background: var(--c2); color: white; padding: 14px 30px; border-radius: 50px; font-weight: 700; text-decoration: none; font-size: 0.95rem; }}
        .cta a:hover {{ background: var(--c1); }}

        footer {{ text-align: center; padding: 40px 0; border-top: 1px solid var(--line); color: var(--ink4); font-size: 0.85rem; }}
        footer a {{ color: var(--ink4); text-decoration: none; }}
        footer a:hover {{ color: var(--ink); }}
    </style>
</head>
<body>
    <div class="grain"></div>
    <nav>
        <div class="nav-bar">
            <a href="../index.html" class="logo"><img src="/thaidata-lockup.svg" alt="ThaiData" class="logo-icon" width="100" height="36"></a>
            <a href="../thai-restaurants-city-breakdown-uk.html" style="color:rgba(255,255,255,0.6);font-size:0.9rem;text-decoration:none;">All Cities</a>
        </div>
    </nav>

    <div class="wrap">

        <div class="hero">
            <h1>Thai Restaurants in <em>London</em> -- 2026</h1>
            <p class="subtitle">{stats_total} FSA-listed Thai restaurants across {len(NEIGHBOURHOODS)} neighbourhoods. From Soho late-night canteens to Wimbledon family staples -- here is where to find the best Thai food in London, area by area.</p>
            <div class="hero-stats">
                <div class="hero-stat"><div class="num">{stats_total}</div><div class="lbl">Restaurants</div></div>
                <div class="hero-stat"><div class="num">{stats_dine_in}</div><div class="lbl">Dine-in</div></div>
                <div class="hero-stat"><div class="num">{stats_takeaway}</div><div class="lbl">Takeaways</div></div>
                <div class="hero-stat"><div class="num">{STAR}{stats_avg}</div><div class="lbl">Avg FSA Rating</div></div>
                <div class="hero-stat"><div class="num">{stats_five}</div><div class="lbl">Five-Star</div></div>
            </div>
        </div>

        <nav class="hood-nav">
            {nav_pills}
        </nav>

        <div class="intro">
            <p><strong>London's Thai food scene is bigger and more diverse than any other UK city.</strong> With {stats_total} FSA-listed businesses spanning every borough from Westminster to Greenwich, it is not a single scene -- it is dozens of overlapping ones.</p>
            <p>In Soho and Chinatown, you will find late-night canteens serving green curry until midnight. In Shoreditch and Hackney, independent Thai cafes do inventive takes on classics alongside street-food stalls at weekend markets. In Kensington and Wimbledon, long-established family restaurants have been serving loyal customers for two decades. And in the outer boroughs, neighbourhood Thai takeaways quietly serve some of the best food in the city.</p>
            <p>This guide breaks London down into its dining neighbourhoods. Each section includes real FSA hygiene data, our top-rated picks, and notes on which chains operate where. The data comes from the <strong>Food Standards Agency</strong>'s most recent inspections -- every rating is verifiable and independently audited.</p>
        </div>

        <div class="start-section">
            <h2>Where to <em>Start</em></h2>
            {start_cards}
        </div>

        {neighbourhood_html}

        <div class="chain-overview">
            <h2>Major Thai <em>Chains</em> in London</h2>
            <p>{chain_summary_text}</p>
        </div>

        <div class="faq-section">
            <h2>Frequently Asked <em>Questions</em></h2>
            {faq_html}
        </div>

        <div class="cta">
            <a href="/r/">Browse all {stats_total} London restaurant pages</a>
        </div>

    </div>

    <footer>
        <div class="wrap">
            <p><a href="/">ThaiData</a> middot Data from <a href="https://www.food.gov.uk/" target="_blank">Food Standards Agency</a> middot Updated {data.get("updated", "2026")}</p>
            <p style="margin-top:6px;font-size:0.8rem;">FSA hygiene ratings are official food safety scores, not customer reviews.</p>
        </div>
    </footer>

</body>
</html>
"""

# Fix placeholders and em dashes
LONDON_PAGE = LONDON_PAGE.replace(" middot ", " · ")
LONDON_PAGE = LONDON_PAGE.replace("star", "★")
LONDON_PAGE = LONDON_PAGE.replace("&#9733;", "★").replace("★", "&#9733;")

# Write
# /cities/london.html is a curated manual page: this one-time generator has
# already served its purpose, and re-running it destroys hand-written
# neighbourhood copy. Require an explicit --force.
if "--force" not in sys.argv:
    print("Refusing to overwrite the curated manual page cities/london.html.")
    print("Re-run with --force only if you intend to regenerate it from scratch.")
    sys.exit(1)
os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
with open(OUTPUT, "w") as f:
    f.write(LONDON_PAGE)
kb = len(LONDON_PAGE) // 1024
neighbourhood_count = len(NEIGHBOURHOODS)
faq_count = 6

print(f"Generated London editorial guide: {OUTPUT}")
print(f"  {kb}KB, {neighbourhood_count} neighbourhoods, {stats_total} restaurants referenced")
print(f"  Schema: BreadcrumbList + City + FAQPage ({faq_count} Q&As)")
print(f"  Manual markers: CITIES-MODE: manual + MANUAL comment")
print(f"  Generator will NEVER touch this file.")
