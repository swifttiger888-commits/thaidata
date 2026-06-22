#!/usr/bin/env python3
"""City page generator — enriches /cities/[slug] pages with schema, content, and data.

Reads .cities.json registry and enforces page mode rules:
  - manual:  never touched
  - hybrid:  only AUTO blocks replaced
  - programmatic: full page generation
  - quarantined:  skipped until resolved

Usage:
    python scripts/generate_city_pages.py                  # Dry run (--dry-run)
    python scripts/generate_city_pages.py --apply           # Write changes
    python scripts/generate_city_pages.py --apply --city manchester  # Single city
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Literal

# Add repo root to path
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.schema.local_business import build_restaurant_list
from scripts.schema.faq_page import build_faq_page
from scripts.schema.breadcrumb import city_breadcrumb
from scripts.schema.city_entity import build_city_entity
from scripts.schema.validator import validate_schema, validate_content_schema_match, strip_html_body

# ── Constants ──────────────────────────────────────────────────────────────────

CITIES_DIR = REPO / "cities"
REGISTRY_PATH = CITIES_DIR / ".cities.json"
DATA_PATH = REPO / "data" / "restaurants.json"
SCHEMAS_DIR = REPO / "schemas"
BUILD_MANIFEST_PATH = CITIES_DIR / ".build-manifest.json"
BASE_URL = "https://thaidata.uk"

# Tier thresholds
ENRICHED_MIN = 13
ENRICHED_MAX = 35  # Above this = considered large enough for bespoke (London)

AUTO_ZONES = {
    "schema",
    "market-snapshot",
    "chain-presence",
    "postcode-areas",
    "faq",
}

# Chain keywords for detection (lowercase)
CHAIN_KEYWORDS: list[str] = [
    "giggling squid",
    "rosa's thai",
    "busaba",
    "thaikhun",
    "camile thai",
    "thai express",
    "thai cottage",
    "thai house",
    "sabai",
    "chaophraya",
    "mango tree",
    "patara",
    "bangkok",
]

# Schema JSON files for validation
SCHEMA_FILES: dict[str, Path] = {
    "ItemList": SCHEMAS_DIR / "item-list.schema.json",
    "FAQPage": SCHEMAS_DIR / "faq-page.schema.json",
}


# ── Slug helpers ────────────────────────────────────────────────────────────────

def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s)
    return s.strip("-")


# ── Loaders ─────────────────────────────────────────────────────────────────────

def load_registry() -> dict[str, Any]:
    """Load .cities.json registry."""
    if not REGISTRY_PATH.exists():
        print(f"  ⚠️  No registry found at {REGISTRY_PATH}")
        return {"version": 1, "cities": {}}
    with open(REGISTRY_PATH) as f:
        return json.load(f)


def save_registry(registry: dict[str, Any]) -> None:
    """Write .cities.json."""
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_restaurants() -> dict[str, Any]:
    """Load restaurants.json and group by city, excluding moderated venues."""
    with open(DATA_PATH) as f:
        data = json.load(f)

    # Load exclusions (moderation layer)
    excluded_ids: set[int] = set()
    excl_path = REPO / "data" / "exclusions.json"
    if excl_path.exists():
        with open(excl_path) as f:
            excl_data = json.load(f)
        excluded_ids.update(excl_data.get("excluded_fsa_ids", []))

    by_city: dict[str, list[dict[str, Any]]] = defaultdict(list)
    total_excluded = 0
    for r in data.get("restaurants", []):
        if r["id"] in excluded_ids:
            total_excluded += 1
            continue
        by_city[r["city"]].append(r)

    return {
        "raw": data,
        "by_city": dict(by_city),
        "total": len(data.get("restaurants", [])),
        "updated": data.get("updated", ""),
    }


def detect_chains(restaurants: list[dict[str, Any]]) -> list[str]:
    """Detect chain names in a city's restaurant list."""
    found: set[str] = set()
    for r in restaurants:
        name_lower = r.get("name", "").lower()
        for chain in CHAIN_KEYWORDS:
            if chain in name_lower:
                found.add(chain.title())
    return sorted(found)


def get_postcode_areas(restaurants: list[dict[str, Any]]) -> dict[str, int]:
    """Group restaurants by outward postcode code."""
    areas: dict[str, int] = defaultdict(int)
    for r in restaurants:
        pc = r.get("postcode", "").strip()
        if pc:
            # Outward code: first part of postcode (e.g. "M4" from "M4 6BG")
            match = re.match(r"([A-Z0-9]+)", pc)
            if match:
                outward = match.group(1)
                areas[outward] += 1
    return dict(sorted(areas.items(), key=lambda x: -x[1]))


# ── City data computation ──────────────────────────────────────────────────────

def compute_city_stats(restaurants: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute statistics for a city."""
    count = len(restaurants)
    dine_in = sum(1 for r in restaurants if r.get("type") == "restaurant")
    takeaway = count - dine_in

    ratings = []
    for r in restaurants:
        try:
            val = int(r.get("hygiene_rating", "0") or "0")
            if 1 <= val <= 5:
                ratings.append(val)
        except (ValueError, TypeError):
            pass

    avg_rating = sum(ratings) / len(ratings) if ratings else 0.0
    min_rating = min(ratings) if ratings else 0
    max_rating = max(ratings) if ratings else 0
    five_star = sum(1 for r in ratings if r == 5)

    def rating_sort_key(r: dict[str, Any]) -> int:
        val = r.get("hygiene_rating", "0")
        try:
            return -int(val)
        except (ValueError, TypeError):
            return 1  # Non-numeric ratings at end

    sorted_restaurants = sorted(
        restaurants,
        key=lambda r: (rating_sort_key(r), r.get("name", "").lower()),
    )

    chains = detect_chains(restaurants)
    postcode_areas = get_postcode_areas(restaurants)

    # Clean restaurant names (collapse double spaces from source data)
    def _clean_name(name: str) -> str:
        return " ".join(name.split())

    return {
        "count": count,
        "dine_in": dine_in,
        "takeaway": takeaway,
        "avg_rating": round(avg_rating, 1),
        "min_rating": min_rating,
        "max_rating": max_rating,
        "five_star": five_star,
        "sorted_restaurants": sorted_restaurants,
        "top_names": [_clean_name(r["name"]) for r in sorted_restaurants[:5]],
        "chains": chains,
        "postcode_areas": postcode_areas,
    }


# ── Mode detection ──────────────────────────────────────────────────────────────

def detect_html_mode(html: str) -> str | None:
    """Detect mode from HTML safeguard markers (full-file scan)."""
    if "<!-- MANUAL -->" in html:
        return "manual"
    match = re.search(r"<!--\s*CITIES-MODE:\s*(\w+)\s*-->", html)
    if match:
        return match.group(1)
    return None


def resolve_mode(
    registry: dict[str, Any],
    slug: str,
    html: str | None,
) -> tuple[Literal["programmatic", "hybrid", "manual", "quarantined"], str | None]:
    """Resolve the mode for a city page.

    Returns (mode, error_reason). If error_reason is set, mode = quarantined.

    Precedence:
        1. HTML <!-- MANUAL --> marker (highest)
        2. HTML <!-- CITIES-MODE: X --> comment
        3. .cities.json registry mode (lowest)
    """
    registry_entry = registry.get("cities", {}).get(slug, {})
    registry_mode = registry_entry.get("mode", "programmatic")

    # Check existing quarantine
    if registry_entry.get("quarantined"):
        return ("quarantined", registry_entry.get("quarantine_reason", "Previously quarantined"))

    # No HTML file yet — treat as programmatic
    if html is None:
        return ("programmatic", None)

    html_mode = detect_html_mode(html)

    # HTML <!-- MANUAL --> is absolute override
    if html_mode == "manual":
        if registry_mode != "manual":
            return (
                "quarantined",
                f"HTML says manual but registry says {registry_mode} — conflict",
            )
        return ("manual", None)

    # HTML comment from a previous generator run should match registry
    if html_mode and html_mode != registry_mode:
        return (
            "quarantined",
            f"HTML mode ({html_mode}) differs from registry mode ({registry_mode}) — conflict",
        )

    # If HTML has no mode comment, use registry
    return (registry_mode, None)


# ── Schema building ─────────────────────────────────────────────────────────────

def build_all_schema(
    city: str,
    city_slug: str,
    stats: dict[str, Any],
    city_count_rank: int,
) -> list[dict[str, Any]]:
    """Build all schema blocks for a city page.

    Returns list of schema dicts. Each is already validated.
    """
    schemas: list[dict[str, Any]] = []

    # 1. BreadcrumbList
    schemas.append(city_breadcrumb(city, city_slug))

    # 2. City entity (if Wikidata entry exists)
    city_entity = build_city_entity(city, city_slug)
    if city_entity:
        schemas.append(city_entity)

    # 3. Restaurant ItemList (top 10)
    item_list = build_restaurant_list(
        city, stats["sorted_restaurants"], max_items=10, base_url=BASE_URL,
    )
    schemas.append(item_list)

    # 4. FAQPage
    faq = build_faq_page(
        city=city,
        count=stats["count"],
        avg_rating=stats["avg_rating"],
        rank=city_count_rank,
        min_rating=stats["min_rating"],
        max_rating=stats["max_rating"],
        dine_in=stats["dine_in"],
        takeaway=stats["takeaway"],
        top_restaurant_names=stats["top_names"],
        chains=stats["chains"] if stats["chains"] else None,
    )
    schemas.append(faq)

    return schemas


def validate_all_schema(schemas: list[dict[str, Any]]) -> list[str]:
    """Validate all schema blocks. Returns list of errors."""
    errors: list[str] = []
    for s in schemas:
        stype = s.get("@type", "?")
        schema_file = SCHEMA_FILES.get(stype)
        schema_errors = validate_schema(s, schema_file)
        for e in schema_errors:
            errors.append(f"[{stype}] {e}")
    return errors


# ── HTML generation helpers ────────────────────────────────────────────────────

def build_schema_html(schemas: list[dict[str, Any]]) -> str:
    """Build the <!-- AUTO:schema --> block content."""
    parts: list[str] = []
    for s in schemas:
        json_str = json.dumps(s, ensure_ascii=False, indent=None)
        parts.append(
            f'<script type="application/ld+json">{json_str}</script>'
        )
    return "\n".join(parts)


def update_hero_stats(html: str, city: str, stats: dict[str, Any], total_uk: int) -> str:
    """Update stale hero-section numbers to match current (post-exclusion) stats.

    The hero section on hybrid/programmatic city pages predates the exclusion
    system.  Its hard-coded counts drift out of sync whenever a restaurant is
    excluded.  This function performs targeted regex replacements so the hero
    always reflects post-exclusion reality — without needing AUTO-zone markers
    in the hero itself.
    """
    count = stats["count"]
    dine_in = stats["dine_in"]
    takeaway = stats["takeaway"]
    avg_rating = stats["avg_rating"]

    # 1. city-stats div:  "14 (13 dine-in, 1 takeaway)"  → fresh numbers
    raw_count = stats.get("_raw_count", count)
    raw_dine_in = stats.get("_raw_dine_in", dine_in)
    raw_takeaway = stats.get("_raw_takeaway", takeaway)
    html = re.sub(
        r'(Thai businesses:</strong> <span[^>]*>)\d+\s*\(\d+ dine-in, \d+ takeaway\)',
        f'\\g<1>{raw_count} ({raw_dine_in} dine-in, {raw_takeaway} takeaway)',
        html,
    )
    # 2. sub paragraph:  "13 FSA-registered Thai businesses"
    html = re.sub(
        r'(<p class="sub">)\d+( FSA-registered Thai businesses)',
        f'\\g<1>{count}\\g<2>',
        html,
    )
    # 3. stat-row: four <div class="num"> blocks inside stat-row div
    stars = "★" * round(avg_rating) if avg_rating else ""
    # Instead of fragile count=1, replace the whole stat-row block
    stat_row_html = (
        '<div class="stat-row">\n'
        '            <div class="stat">\n'
        f'                <div class="num">{count}</div>\n'
        '                <div class="lbl">Total Thai Businesses</div>\n'
        '            </div>\n'
        '            <div class="stat">\n'
        f'                <div class="num">{dine_in}</div>\n'
        '                <div class="lbl">Dine-in Restaurants</div>\n'
        '            </div>\n'
        '            <div class="stat">\n'
        f'                <div class="num">{takeaway}</div>\n'
        '                <div class="lbl">Takeaways</div>\n'
        '            </div>\n'
        '            <div class="stat">\n'
        f'                <div class="num">{stars}</div>\n'
        '                <div class="lbl">Avg Hygiene Rating</div>\n'
        '            </div>\n'
        '        </div>'
    )
    html = re.sub(
        r'<div class="stat-row">.*?</div>\s*</div>\s*\n\s*<div class="card">',
        stat_row_html + '\n\n        <div class="card">',
        html,
        flags=re.DOTALL,
    )
    # 4. Market Overview:  "13 Thai food businesses"
    html = re.sub(
        r'(has <strong>)\d+( Thai food businesses</strong>)',
        f'\\g<1>{count}\\g<2>',
        html,
    )
    # 5. Market Position vs London / UK total
    uk_total = total_uk
    london_count = stats.get("_london_count", 0)  # set by caller if available
    if london_count:
        html = re.sub(
            r"(London's )\d+( Thai businesses)",
            f"\\g<1>{london_count}\\g<2>",
            html,
        )
    if uk_total:
        html = re.sub(
            r'(all )[\d,]+( FSA-registered Thai businesses across the UK)',
            f'\\g<1>{uk_total}\\g<2>',
            html,
        )
        html = re.sub(
            r'(all )[\\d,]+( UK Thai businesses)',
            f'\\g<1>{uk_total}\\g<2>',
            html,
        )
        html = re.sub(
            r'(accounts for [\\d.]+% of all )[\\d,]+( FSA-registered Thai businesses)',
            f'\\g<1>{uk_total}\\g<2>',
            html,
        )

    return html


def build_market_snapshot_html(city: str, stats: dict[str, Any]) -> str:
    """Build the market-snapshot AUTO block."""
    businesses = stats["count"]
    pop_word = "businesses" if businesses != 1 else "business"
    return (
        '<div class="card">\n'
        '  <h2>Market <em>Snapshot</em></h2>\n'
        f'  <p>There {("is" if businesses == 1 else "are")} <strong>{businesses}</strong> '
        f'FSA-registered Thai {pop_word} in <strong>{city}</strong>. '
        f'Average hygiene rating: \u2605{stats["avg_rating"]}/5. '
        f'{stats["dine_in"]} dine-in, {stats["takeaway"]} takeaway.</p>\n'
        f'  <p style="margin-top:10px;font-size:0.88rem;">\n'
        f'    <a href="/dish-prices" style="color:var(--c2);">Compare dish prices</a>'
        f' &middot; '
        f'<a href="/chains/" style="color:var(--c2);">Explore chain profiles</a>'
        f' &middot; '
        f'<a href="/thai-restaurants-city-breakdown-uk" style="color:var(--c2);">View all cities</a>\n'
        f'  </p>\n'
        '</div>'
    )



def build_chain_presence_html(city: str, chains: list[str], count: int) -> str:
    """Build the chain-presence AUTO block."""
    if not chains:
        return ""
    chain_list = ", ".join(chains)
    independent = count - len(chains)
    return (
        '<div class="card">\n'
        '  <h2>Chain <em>Presence</em></h2>\n'
        f'  <p>Major Thai chains in {city}: <strong>{chain_list}</strong>.</p>\n'
        f'  <p style="color:var(--ink3);">The remaining {independent} '
        f'{"business is" if independent == 1 else "businesses are"} independent.</p>\n'
        f'  <p style="margin-top:10px;"><a href="/chains/" '
        f'style="color:var(--c2);text-decoration:underline;text-underline-offset:2px;">'
        f'View the complete UK Thai chain directory</a> &mdash; '
        f'location counts, city presence, and hygiene profiles for 12 major chains.</p>\n'
        '</div>'
    )


def build_postcode_areas_html(areas: dict[str, int], city: str) -> str:
    """Build the postcode-areas AUTO block."""
    if not areas:
        return ""
    top_areas = list(areas.items())[:5]
    items = "".join(
        f'<li style="padding:4px 0;color:var(--ink4);">'
        f'<strong>{code}</strong> — {count} Thai food {business}</li>\n'
        for code, count in top_areas
        for business in [("business" if count == 1 else "businesses")]
    )
    return (
        '<div class="card">\n'
        '  <h2>Popular Dining <em>Postcodes</em></h2>\n'
        f'  <p>Thai restaurants in {city} cluster in these postcode areas:</p>\n'
        f'  <ul style="padding-left:20px;">\n{items}  </ul>\n'
        '</div>'
    )


def build_faq_html(schemas: list[dict[str, Any]]) -> str:
    """Build the FAQ AUTO block from the FAQPage schema."""
    faq_schema = next((s for s in schemas if s.get("@type") == "FAQPage"), None)
    if not faq_schema:
        return ""
    items = ""
    for qa in faq_schema.get("mainEntity", []):
        question = qa.get("name", "")
        answer = qa.get("acceptedAnswer", {}).get("text", "")
        items += (
            f'<details style="margin:8px 0;padding:12px 16px;'
            f'background:rgba(255,255,255,0.02);border:1px solid var(--line);'
            f'border-radius:10px;">\n'
            f'  <summary style="cursor:pointer;font-weight:600;color:white;">'
            f'{question}</summary>\n'
            f'  <p style="margin-top:8px;color:var(--ink4);">{answer}</p>\n'
            f'</details>\n'
        )
    return (
        '<div class="card">\n'
        '  <h2>Frequently Asked <em>Questions</em></h2>\n'
        f'{items}'
        f'  <p style="margin-top:12px;"><a href="/faq" '
        f'style="color:var(--c2);text-decoration:underline;text-underline-offset:2px;">'
        f'More UK Thai restaurant FAQs</a> &mdash; '
        f'hygiene ratings, pricing guides, delivery platforms, and data methodology.</p>\n'
        '</div>'
    )


# ── AUTO block management ─────────────────────────────────────────────────────

AUTO_RE = re.compile(
    r"<!--\s*AUTO:(\w+)\s*-->(.*?)<!--\s*END:AUTO:\1\s*-->",
    re.DOTALL,
)

SINGLE_AUTO_OPEN_RE = re.compile(r"<!--\s*AUTO:(\w+)\s*-->")
SINGLE_AUTO_CLOSE_RE = re.compile(r"<!--\s*END:AUTO:(\w+)\s*-->")


def extract_auto_zones(html: str) -> dict[str, str] | str:
    """Extract existing AUTO zones from HTML.

    Returns dict of {name: full_match_text} on success.
    Returns error string on failure (missing/duplicate/nested markers).
    """
    # Check for nested markers
    for zone in AUTO_ZONES:
        pattern = rf"<!--\s*AUTO:{re.escape(zone)}\s*-->.*?<!--\s*AUTO:{re.escape(zone)}\s*-->"
        if re.search(pattern, html, re.DOTALL):
            return f"Duplicate AUTO:{zone} markers found"

    # Check for orphan close markers
    open_markers = set(SINGLE_AUTO_OPEN_RE.findall(html))
    close_markers = set(SINGLE_AUTO_CLOSE_RE.findall(html))
    if open_markers != close_markers:
        only_open = open_markers - close_markers
        only_close = close_markers - open_markers
        parts = []
        if only_open:
            parts.append(f"missing END:AUTO for zones: {only_open}")
        if only_close:
            parts.append(f"unmatched END:AUTO for zones: {only_close}")
        return "; ".join(parts)

    # Check for nesting
    for match in AUTO_RE.finditer(html):
        zone_name = match.group(1)
        inner = match.group(2)
        if AUTO_RE.search(inner):
            return f"Nested AUTO markers inside AUTO:{zone_name}"

    zones: dict[str, str] = {}
    for match in AUTO_RE.finditer(html):
        zones[match.group(1)] = match.group(0)

    # Check for unrecognised zones
    unknown = set(zones.keys()) - AUTO_ZONES
    if unknown:
        return f"Unrecognised AUTO zones: {unknown}"

    return zones


def inject_auto_zones(html: str, zone_name: str, content: str) -> str:
    """Replace an existing AUTO zone, or append it before </body> if not found."""
    pattern = rf"<!--\s*AUTO:{re.escape(zone_name)}\s*-->.*?<!--\s*END:AUTO:{re.escape(zone_name)}\s*-->"
    replacement = f"<!-- AUTO:{zone_name} -->\n{content}\n<!-- END:AUTO:{zone_name} -->"

    if re.search(pattern, html, re.DOTALL):
        return re.sub(pattern, replacement, html, count=1, flags=re.DOTALL)

    # Not found — append before </body>
    print(f"  ℹ️  AUTO:{zone_name} not found — appending before </body>")
    return html.replace(
        "</body>",
        f"{replacement}\n</body>",
    )


def strip_auto_zones(html: str) -> str:
    """Remove all AUTO zones from HTML (used during transition to manual)."""
    return AUTO_RE.sub("", html)


# ── Ranking ────────────────────────────────────────────────────────────────────

def compute_national_rank(by_city: dict[str, list], city_name: str) -> int:
    """Compute national rank by restaurant count (1-based)."""
    city_counts = [(city, len(rests)) for city, rests in by_city.items()]
    city_counts.sort(key=lambda x: -x[1])
    for i, (city, _) in enumerate(city_counts, 1):
        if city == city_name:
            return i
    return len(city_counts)


# ── Per-city processing ────────────────────────────────────────────────────────

def process_city(
    slug: str,
    city_name: str,
    registry: dict[str, Any],
    all_data: dict[str, Any],
    dry_run: bool = False,
) -> dict[str, Any]:
    """Process a single city page.

    Returns status dict:
        {"slug": slug, "action": "skipped"|"generated"|"quarantined", "errors": [...]}
    """
    result: dict[str, Any] = {
        "slug": slug,
        "action": "skipped",
        "errors": [],
        "warnings": [],
    }

    by_city = all_data["by_city"]
    restaurants = by_city.get(city_name, [])

    if not restaurants:
        result["action"] = "quarantined"
        result["errors"].append(f"No restaurant data for city: {city_name}")
        return result

    # Read existing HTML (if any)
    html_path = CITIES_DIR / f"{slug}.html"
    existing_html: str | None = None
    if html_path.exists():
        with open(html_path) as f:
            existing_html = f.read()

    # Resolve mode
    mode, error = resolve_mode(registry, slug, existing_html)
    if mode == "quarantined":
        result["action"] = "quarantined"
        result["errors"].append(error or "Quarantined by mode resolver")
        return result

    if mode == "manual":
        result["action"] = "skipped"
        return result

    # Compute statistics
    stats = compute_city_stats(restaurants)
    rank = compute_national_rank(by_city, city_name)

    # Compute totals needed for hero-stat updates
    total_uk = len(all_data["raw"].get("restaurants", []))
    london_restaurants = by_city.get("London", [])
    stats["_london_count"] = len(london_restaurants)
    # Raw count including excluded (for city-stats div which shows FSA total)
    raw_city = [r for r in all_data["raw"].get("restaurants", []) if r.get("city") == city_name]
    stats["_raw_count"] = len(raw_city)
    stats["_raw_dine_in"] = sum(1 for r in raw_city if r.get("type") == "restaurant")
    stats["_raw_takeaway"] = stats["_raw_count"] - stats["_raw_dine_in"]

    # Build schema
    schemas = build_all_schema(city_name, slug, stats, rank)
    schema_errors = validate_all_schema(schemas)
    if schema_errors:
        result["action"] = "quarantined"
        result["errors"].extend(schema_errors)
        return result

    if dry_run:
        result["action"] = "would-generate"
        result["mode"] = mode
        result["stats"] = {
            "count": stats["count"],
            "chains": len(stats["chains"]),
            "postcode_areas": len(stats["postcode_areas"]),
            "schema_blocks": len(schemas),
        }
        return result

    # ── Generate / update HTML ──

    html = existing_html or f"<!DOCTYPE html>\n<html lang=\"en-GB\">\n<head>\n<title>Thai Restaurants in {city_name} | ThaiData</title>\n</head>\n<body>\n</body>\n</html>"

    # Update stale hero-section numbers (pre-dates exclusion system)
    if existing_html and mode in ("programmatic", "hybrid"):
        html = update_hero_stats(html, city_name, stats, total_uk)

    # Add mode comment if not present
    if f"CITIES-MODE: {mode}" not in html:
        mode_comment = f"<!-- CITIES-MODE: {mode} -->\n"
        html = re.sub(r"(<html[^>]*>)", rf"\1\n{mode_comment}", html)

    # Manage AUTO zones
    zones = extract_auto_zones(html)
    if isinstance(zones, str):
        # Error — quarantine
        result["action"] = "quarantined"
        result["errors"].append(f"Marker integrity error: {zones}")
        return result

    # Strip pre-existing schema blocks outside AUTO zones (they'll be re-injected
    # in the AUTO:schema section with richer content). This prevents duplicate
    # BreadcrumbList, City, etc. from the old template.
    auto_section_match = re.search(r"<!-- AUTO:schema -->", html)
    schema_to_remove: list[tuple[int, int]] = []
    for match in re.finditer(
        r'<script\s+type="application/ld\+json"[^>]*>.*?</script>',
        html,
        re.DOTALL,
    ):
        script_start = match.start()
        script_end = match.end()
        # Check if inside AUTO:schema zone
        if auto_section_match and script_start > auto_section_match.start():
            continue  # Inside AUTO zone — keep
        # Outside — mark for removal
        schema_to_remove.append((script_start, script_end))

    # Remove from end to start to preserve positions
    for start, end in reversed(schema_to_remove):
        html = html[:start] + html[end:]

    if mode == "programmatic":
        # Replace or inject all AUTO zones
        html = inject_auto_zones(html, "schema", build_schema_html(schemas))
        html = inject_auto_zones(html, "market-snapshot", build_market_snapshot_html(city_name, stats))
        if stats["chains"]:
            html = inject_auto_zones(html, "chain-presence", build_chain_presence_html(city_name, stats["chains"], stats["count"]))
        if stats["postcode_areas"]:
            html = inject_auto_zones(html, "postcode-areas", build_postcode_areas_html(stats["postcode_areas"], city_name))
        html = inject_auto_zones(html, "faq", build_faq_html(schemas))

    elif mode == "hybrid":
        # Replace existing AUTO zones + inject new ones needed for enrichment
        for zone_name, zone_content_fn in [
            ("schema", lambda: build_schema_html(schemas)),
            ("market-snapshot", lambda: build_market_snapshot_html(city_name, stats)),
            ("chain-presence", lambda: build_chain_presence_html(city_name, stats["chains"], stats["count"]) if stats["chains"] else None),
            ("postcode-areas", lambda: build_postcode_areas_html(stats["postcode_areas"], city_name) if stats["postcode_areas"] else None),
            ("faq", lambda: build_faq_html(schemas)),
        ]:
            content = zone_content_fn()
            if content is None:
                continue  # No data for this zone
            if zone_name in zones:
                html = inject_auto_zones(html, zone_name, content)
            else:
                # New zone for hybrid page — inject with info log
                print(f"  ℹ️  Injecting AUTO:{zone_name} on hybrid page")
                html = inject_auto_zones(html, zone_name, content)

    # Content–schema matching
    visible_text = strip_html_body(html)
    for s in schemas:
        match_errors = validate_content_schema_match(visible_text, s, raw_html=html)
        if match_errors:
            result["warnings"].extend(match_errors)

    # Write
    with open(html_path, "w") as f:
        f.write(html)

    result["action"] = "generated"
    result["mode"] = mode
    return result


# ── Main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="City page generator")
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry run)")
    parser.add_argument("--city", type=str, help="Process only one city slug")
    args = parser.parse_args()

    registry = load_registry()
    all_data = load_restaurants()
    by_city = all_data["by_city"]

    # Build city name → slug mapping
    name_to_slug: dict[str, str] = {}
    for city in by_city:
        name_to_slug[slugify(city)] = city

    results: list[dict[str, Any]] = []
    quarantined_count = 0
    generated_count = 0
    skipped_count = 0

    if args.city:
        # Single city mode
        target_slug = args.city.lower()
        city_name = name_to_slug.get(target_slug)
        if not city_name:
            print(f"❌ City not found: {target_slug}")
            sys.exit(1)
        cities_to_process = [(target_slug, city_name)]
    else:
        # All cities from registry
        cities_to_process = []
        for slug, entry in registry.get("cities", {}).items():
            city_name = name_to_slug.get(slug, slug.replace("-", " ").title())
            cities_to_process.append((slug, city_name))

        # Discover new cities from data not in registry
        registry_slugs = set(registry.get("cities", {}))
        for city in by_city:
            slug = slugify(city)
            if slug not in registry_slugs:
                print(f"  📦 New city discovered: {city} ({slug})")
                registry.setdefault("cities", {})[slug] = {
                    "tier": "enriched" if len(by_city[city]) >= ENRICHED_MIN else "standard",
                    "mode": "hybrid" if len(by_city[city]) >= ENRICHED_MIN else "programmatic",
                    "quarantined": False,
                    "restaurant_count": len(by_city[city]),
                    "transitions": [
                        {"from": None, "to": "programmatic", "date": str(date.today()), "reason": "Auto-created from new restaurant data"}
                    ],
                }
                cities_to_process.append((slug, city))

    print(f"\n{'='*50}")
    print(f"  City Page Generator — {'DRY RUN' if not args.apply else 'APPLY'}")
    print(f"  {date.today().isoformat()}")
    print(f"{'='*50}\n")

    for slug, city_name in sorted(cities_to_process):
        if not args.city and slug in ("other-uk",):
            continue  # Skip pseudo-cities

        result = process_city(
            slug=slug,
            city_name=city_name,
            registry=registry,
            all_data=all_data,
            dry_run=not args.apply,
        )
        results.append(result)

        action = result["action"]
        if action == "quarantined":
            quarantined_count += 1
            print(f"  ❌ {slug} — QUARANTINED")
            for e in result.get("errors", []):
                print(f"     {e}")
        elif action == "generated":
            generated_count += 1
            print(f"  ✅ {slug} — generated ({result.get('mode', '?')})")
            for w in result.get("warnings", []):
                print(f"     ⚠️  {w}")
        elif action == "would-generate":
            generated_count += 1
            stats = result.get("stats", {})
            print(f"  🔷 {slug} — would generate ({result.get('mode', '?')}, "
                  f"{stats.get('count', 0)} restaurants, "
                  f"{stats.get('schema_blocks', 0)} schema blocks)")
        elif action == "skipped":
            skipped_count += 1

    # Summary
    print(f"\n{'='*50}")
    print(f"  Summary: {generated_count} generated, {quarantined_count} quarantined, {skipped_count} skipped")
    print(f"{'='*50}")

    # Build manifest
    manifest = {
        "run_date": str(date.today()),
        "applied": args.apply,
        "total_cities": len(cities_to_process),
        "generated": generated_count,
        "quarantined": quarantined_count,
        "skipped": skipped_count,
        "quarantined_pages": [
            {"slug": r["slug"], "reason": r.get("errors", ["Unknown"])[0]}
            for r in results if r["action"] == "quarantined"
        ],
    }
    if args.apply:
        with open(BUILD_MANIFEST_PATH, "w") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
            f.write("\n")
        # Update registry transitions for generated pages
        registry_changed = False
        for r in results:
            if r["action"] == "generated":
                entry = registry.setdefault("cities", {}).setdefault(r["slug"], {})
                prev_mode = entry.get("mode", "unknown")
                new_mode = r.get("mode", prev_mode)
                if prev_mode != new_mode:
                    entry.setdefault("transitions", []).append({
                        "from": prev_mode,
                        "to": new_mode,
                        "date": str(date.today()),
                        "reason": "Generator run",
                    })
                    entry["mode"] = new_mode
                    registry_changed = True
        if registry_changed:
            save_registry(registry)

    # Return exit code 0 (quarantines are expected, not failures)
    sys.exit(0)


if __name__ == "__main__":
    main()
