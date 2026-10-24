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
import subprocess
import sys
from collections import defaultdict
from html import escape as html_escape
from urllib.parse import quote_plus
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

if __package__:
    from .location_shell import new_location_shell, finish_location_shell
else:
    from location_shell import new_location_shell, finish_location_shell

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

# Scottish businesses are inspected under the Food Hygiene Information Scheme
# (FHIS, Food Standards Scotland) and rated Pass / Improvement Required /
# Exempt — never 0–5. Keep them out of numeric averages; label by scheme.
FHIS_STATUSES: tuple[str, ...] = ("Pass", "Improvement Required", "Exempt")

# Schema JSON files for validation
SCHEMA_FILES: dict[str, Path] = {
    "ItemList": SCHEMAS_DIR / "item-list.schema.json",
    "FAQPage": SCHEMAS_DIR / "faq-page.schema.json",
}


# ── Affiliate block (Booking.com) ──────────────────────────────────────────────

AFFILIATE_CONFIG_PATH = REPO / "data" / "affiliates.json"
AFFILIATE_START = "<!-- AFFILIATE:booking -->"
AFFILIATE_END = "<!-- END:AFFILIATE:booking -->"


def load_affiliate_config() -> dict[str, Any]:
    """Load data/affiliates.json; {} when absent or unreadable."""
    if not AFFILIATE_CONFIG_PATH.exists():
        return {}
    with open(AFFILIATE_CONFIG_PATH) as f:
        return json.load(f)


def build_booking_block(city_name: str) -> str:
    """Booking.com 'Where to stay' block, or '' when the feature is disabled."""
    cfg = load_affiliate_config().get("booking", {})
    if not cfg.get("enabled"):
        return ""
    url = cfg["search_url_template"].format(
        aid=cfg["aid"], city=quote_plus(city_name)
    )
    name = html_escape(city_name)
    disclosure = html_escape(cfg.get("disclosure", ""))
    return (
        '    <section class="card affiliate" aria-labelledby="stay-title">\n'
        f'      <h2 id="stay-title">Where to stay in {name}</h2>\n'
        f"      <p>Visiting {name}? Compare hotels and places to stay on Booking.com.</p>\n"
        f'      <a class="button" href="{html_escape(url, quote=True)}" '
        f'rel="sponsored nofollow" data-affiliate="booking">Search hotels in {name}</a>\n'
        f'      <p class="affiliate-note">{disclosure}</p>\n'
        "    </section>"
    )


def inject_affiliate_block(html: str, city_name: str) -> str:
    """Insert/refresh the Booking.com block at the end of <main>.

    Idempotent: refreshes the marked block when present, otherwise inserts
    before the first </main>. Pages without </main> (empty state) are skipped.
    A disabled config removes any existing block and otherwise changes nothing.
    """
    block = build_booking_block(city_name)
    if AFFILIATE_START in html and AFFILIATE_END in html:
        left = html.index(AFFILIATE_START) + len(AFFILIATE_START)
        right = html.index(AFFILIATE_END, left)
        return html[:left] + ("\n" + block + "\n" if block else "") + html[right:]
    if not block or "</main>" not in html:
        return html
    main_end = html.index("</main>")
    return (
        html[:main_end]
        + "\n"
        + AFFILIATE_START
        + "\n"
        + block
        + "\n"
        + AFFILIATE_END
        + "\n"
        + html[main_end:]
    )


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


def build_city_context(all_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Per-city display context + UK baselines for legacy-block refresh.

    Reads api/v1/cities.json (population, per_100k) and derives UK-wide
    baselines from current data.
    """
    ctx: dict[str, dict[str, Any]] = {}
    uk_density = None
    uk_per_city = None

    cities_path = REPO / "api" / "v1" / "cities.json"
    if cities_path.exists():
        with open(cities_path) as f:
            cdata = json.load(f)
        cities = cdata.get("cities", [])
        for c in cities:
            ctx[c.get("name", "")] = {
                "population": c.get("population"),
                "per_100k": c.get("per_100k"),
            }
        pops = [(c["population"], c["total_thai_businesses"]) for c in cities if c.get("population")]
        if pops:
            sum_p = sum(p for p, _ in pops)
            sum_c = sum(n for _, n in pops)
            if sum_p:
                uk_density = round(sum_c / sum_p * 1e5, 1)
        if cities:
            uk_per_city = len(all_data["raw"].get("restaurants", [])) / len(cities)

    nums = [
        int(r["hygiene_rating"])
        for r in all_data["raw"].get("restaurants", [])
        if str(r.get("hygiene_rating", "")).isdigit()
    ]
    uk_avg = round(sum(nums) / len(nums), 1) if nums else None

    for c in ctx.values():
        c["uk_density"] = uk_density
        c["uk_per_city"] = uk_per_city
        c["uk_avg"] = uk_avg
        c["data_updated"] = all_data.get("updated", "")
    return ctx


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
    # Pubs with Thai kitchens sit outside the restaurant/takeaway totals and get their
    # own count — they are listed in the separate pubs section, never mixed in.
    pubs = [r for r in restaurants if r.get("type") == "pub"]
    core = [r for r in restaurants if r.get("type") != "pub"]
    count = len(core)
    dine_in = sum(1 for r in core if r.get("type") == "restaurant")
    takeaway = sum(1 for r in core if r.get("type") == "takeaway")

    ratings = []
    for r in core:
        try:
            val = int(r.get("hygiene_rating", "0") or "0")
            if 1 <= val <= 5:
                ratings.append(val)
        except (ValueError, TypeError):
            pass

    # FHIS (Scotland): Pass / Improvement Required / Exempt are statuses, not
    # scores. A city is FHIS-rated when none of its businesses carry a numeric
    # score; the numeric helpers stay at 0 and FHIS counts take over.
    fhis_rows = [r for r in core if r.get("hygiene_rating") in FHIS_STATUSES]
    scheme = "FHIS" if (fhis_rows and not ratings) else "FHRS"
    fhis_pass = sum(1 for r in fhis_rows if r.get("hygiene_rating") == "Pass")
    fhis_improvement = sum(1 for r in fhis_rows if r.get("hygiene_rating") == "Improvement Required")
    fhis_exempt = sum(1 for r in fhis_rows if r.get("hygiene_rating") == "Exempt")
    fhis_pass_names = sorted(
        " ".join(r.get("name", "").split())
        for r in fhis_rows
        if r.get("hygiene_rating") == "Pass"
    )

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
        core,
        key=lambda r: (rating_sort_key(r), r.get("name", "").lower()),
    )

    chains = detect_chains(core)
    postcode_areas = get_postcode_areas(core)

    # Clean restaurant names (collapse double spaces from source data)
    def _clean_name(name: str) -> str:
        return " ".join(name.split())

    return {
        "count": count,
        "dine_in": dine_in,
        "takeaway": takeaway,
        "pubs": len(pubs),
        "avg_rating": round(avg_rating, 1),
        "min_rating": min_rating,
        "max_rating": max_rating,
        "five_star": five_star,
        "scheme": scheme,
        "fhis_pass": fhis_pass,
        "fhis_improvement": fhis_improvement,
        "fhis_exempt": fhis_exempt,
        "fhis_pass_names": fhis_pass_names,
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
        scheme=stats.get("scheme", "FHRS"),
        fhis_pass=stats.get("fhis_pass", 0),
        fhis_improvement=stats.get("fhis_improvement", 0),
        fhis_exempt=stats.get("fhis_exempt", 0),
        fhis_pass_names=stats.get("fhis_pass_names", []),
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


def validate_rendered_schema(schema_html: str) -> list[str]:
    """Validate that every ld+json block in schema_html is parseable JSON.

    Returns a list of error strings.  Empty list = all valid.
    Call after build_schema_html() and before injecting into the page.
    """
    errors: list[str] = []
    pattern = re.compile(
        r'<script\s+type="application/ld\+json"[^>]*>(.*?)</script>',
        re.DOTALL,
    )
    for i, match in enumerate(pattern.finditer(schema_html), 1):
        raw = match.group(1)
        try:
            json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(
                f"Schema block {i}: invalid JSON at position {exc.pos} — {exc.msg}"
            )
    return errors


def update_hero_stats(
    html: str,
    city: str,
    stats: dict[str, Any],
    total_uk: int,
    ctx: dict[str, Any] | None = None,
) -> str:
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

    # 0. Strip regex artifacts from previous broken generator runs
    html = re.sub(r'\\g<\d+>', '', html)

    # 1. city-stats div:  "14 (13 dine-in, 1 takeaway)"  → fresh numbers
    raw_count = stats.get("_raw_count", count)
    raw_dine_in = stats.get("_raw_dine_in", dine_in)
    raw_takeaway = stats.get("_raw_takeaway", takeaway)
    html = re.sub(
        r'(Thai businesses:</strong> <span[^>]*>)\d+\s*\(\d+ dine-in, \d+ takeaway\)',
        f'\\g<1>{raw_count} ({raw_dine_in} dine-in, {raw_takeaway} takeaway)',
        html,
    )
    # 2. sub paragraph:  "13 FSA-listed Thai businesses"
    html = re.sub(
        r'(<p class="sub">)\d+( FSA-listed Thai businesses)',
        f'\\g<1>{count}\\g<2>',
        html,
    )
    # 2b. sub paragraph tail:  "★4.4 average hygiene rating · 2.5% of UK total"
    # These two were baked at shell-build time and never refreshed — drift on
    # every data change.  Lookaheads keep the regexes scoped to this sentence.
    if avg_rating:
        html = re.sub(r'★[\d.]+(?= average hygiene rating)', f'★{avg_rating:.1f}', html)
    if total_uk:
        html = re.sub(r'[\d.]+%(?= of UK total)', f'{count / total_uk * 100:.1f}%', html)
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
        r'<div class="stat-row">(?:(?!<div class="(?:stat-row|city-stats|card)")[\s\S])*</div>\s*</div>',
        stat_row_html,
        html,
        count=1,
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
            r'(all )[\d,]+( FSA-listed Thai businesses across the UK)',
            f'\\g<1>{uk_total}\\g<2>',
            html,
        )
        html = re.sub(
            r'(all )[\\d,]+( UK Thai businesses)',
            f'\\g<1>{uk_total}\\g<2>',
            html,
        )
        html = re.sub(
            r'(accounts for [\\d.]+% of all )[\\d,]+( FSA-listed Thai businesses)',
            f'\\g<1>{uk_total}\\g<2>',
            html,
        )

    # ── 5b. Markdown artifacts (**bold**) → real HTML, then the later legacy
    # families (Market Overview paragraph, meta head, FHIS note, vs-UK total) ──
    html = re.sub(r"\*\*([^*<>]{1,90}?)\*\*", r"<strong>\1</strong>", html)

    pop = ctx.get("population")
    uk_density = ctx.get("uk_density")
    raw_count = stats.get("_raw_count", count)

    def _overview(m: "re.Match[str]") -> str:
        parsed_pop = int(m.group(3).replace(",", "")) if m.group(3) else 0
        use_pop = pop or parsed_pop
        if not (use_pop and uk_density):
            return m.group(0)
        density = raw_count / use_pop * 1e5
        diff = density - uk_density
        cmp_word = "above" if diff > 0.3 else ("below" if diff < -0.3 else "in line with")
        biz_word = "business" if raw_count == 1 else "businesses"
        return (
            m.group(1)
            + f"<strong>{raw_count:,} Thai food {biz_word}</strong> "
            + f"serving a population of approximately <strong>{use_pop:,}</strong>. "
            + f"That's <strong>{density:.1f} Thai businesses per 100,000 residents</strong> "
            + f"— {cmp_word} the UK average of {uk_density}/100k."
        )

    html = re.sub(
        r"(<p>[^<]{0,60}? has )<strong>[\d,]+(?: Thai food business(?:es)?)</strong>"
        r"( serving a population of approximately )<strong>([\d,]+)</strong>\. "
        r"That's <strong>[\d.]+(?: Thai businesses per 100,000 residents)</strong>"
        r" — [^<]{0,45}?[\d.]+/100k\.",
        _overview, html,
    )

    # meta head: counts, per-capita density, stars (FHIS-aware)
    html = re.sub(r"(\d+) Thai restaurants & takeaways in ",
                  lambda m: f"{raw_count:,} Thai restaurants & takeaways in ", html)
    per_100k = ctx.get("per_100k")
    if per_100k:
        html = re.sub(r"(Per-capita density \()[\d.]+(/100k\))",
                      lambda m: m.group(1) + f"{per_100k:.1f}" + m.group(2), html)
    if stats.get("scheme", "FHRS") == "FHIS":
        html = re.sub(r"(hygiene ratings \()[★☆]+(\))",
                      r"\1FHIS ratings: Pass/Improvement Required\2", html)
        html = re.sub(r"(<title>[^<]*? — )[\d,]+( Businesses, )[★☆]+( Avg Rating)",
                      lambda m: m.group(1) + f"{raw_count:,}" + m.group(2) + "FHIS Rated", html)
    elif avg_rating:
        n_full = int(avg_rating + 0.5)
        meta_stars = "★" * n_full + "☆" * (5 - n_full)
        html = re.sub(r"(hygiene ratings \()[★☆]+(\))",
                      lambda m: m.group(1) + meta_stars + m.group(2), html)
        html = re.sub(r"(<title>[^<]*? — )[\d,]+( Businesses, )[★☆]+( Avg Rating)",
                      lambda m: m.group(1) + f"{raw_count:,}" + m.group(2) + meta_stars + m.group(3), html)
    html = re.sub(r"(<title>[^<]*? — )[\d,]+( Businesses)",
                  lambda m: m.group(1) + f"{raw_count:,}" + m.group(2), html)

    # ── 6b. Legacy lines the older refresh passes never touched:
    # og:title count/stars, vs-London share percentages, dine-in split ──
    scheme_here = stats.get("scheme", "FHRS")
    if scheme_here == "FHIS":
        html = re.sub(
            r'(property="og:title" content="[^"]*? — )[\d,]+( Businesses)(?:, [^"]* Avg Rating)?"',
            lambda m: m.group(1) + f"{raw_count:,}" + m.group(2) + ', FHIS Rated"',
            html,
        )
    elif avg_rating:
        n_full = int(avg_rating + 0.5)
        meta_stars = "★" * n_full + "☆" * (5 - n_full)
        html = re.sub(
            r'(property="og:title" content="[^"]*? — )[\d,]+( Businesses)(?:, [^"]* Avg Rating)?"',
            lambda m: m.group(1) + f"{raw_count:,}" + m.group(2) + f", {meta_stars} Avg Rating" + '"',
            html,
        )

    # vs London: recompute business-share and population-share percentages
    london_count = stats.get("_london_count", 0)
    london_pop = stats.get("_london_pop")
    pop_vs = ctx.get("population")
    if london_count:
        biz = f"{city} has {count / london_count * 100:.1f}% of London's {london_count:,} Thai businesses"
        if pop_vs and london_pop:
            pop_pct = f"{pop_vs / london_pop * 100:.1f}%"
            london_pop_txt = f"{london_pop / 1e6:.2f}M" if london_pop >= 1e6 else f"{london_pop:,}"
            html = re.sub(
                r"vs London:</strong> [^<]*? has [\d.]+% of London's [\d,]+ Thai businesses, with [\d.]+% of London's [\d.M,]+ population\.</li>",
                f"vs London:</strong> {biz}, with {pop_pct} of London's {london_pop_txt} population.</li>",
                html,
            )
            html = re.sub(
                r"vs London:</strong> [^<]*? has [\d.]+% of London's [\d,]+ Thai businesses, despite having [\d.]+% of London's population\.",
                f"vs London:</strong> {biz}, despite having {pop_pct} of London's population.",
                html,
            )
            html = re.sub(
                r"vs London:</strong> [^<]*? has [\d.]+% of London's [\d,]+ Thai businesses\.",
                f"vs London:</strong> {biz}.",
                html,
            )
        else:
            html = re.sub(
                r"vs London:</strong> [^<]*? has [\d.]+% of London's [\d,]+ Thai businesses[^.]*\.",
                f"vs London:</strong> {biz}. Population data not available for ratio.",
                html,
            )

    # dine-in / takeaway split paragraph + "With N dine-in restaurants" line
    dine_in = stats.get("dine_in", 0)
    takeaway = stats.get("takeaway", 0)
    if count:
        dine_pct = round(dine_in / count * 100)
        html = re.sub(
            r"\d+% of Thai food businesses in [^<]*? are dine-in restaurants \(\d+\), while \d+% are takeaways \(\d+\)\.",
            f"{dine_pct}% of Thai food businesses in {city} are dine-in restaurants ({dine_in}), "
            f"while {100 - dine_pct}% are takeaways ({takeaway}).",
            html,
        )
        html = re.sub(
            r"With \d+ dine-in restaurants",
            f"With {dine_in} dine-in restaurants",
            html,
        )

    # FHIS mapping note → scheme-accurate wording
    html = re.sub(
        r"Note: Scottish ratings use the FHIS scheme[^<]*",
        "Note: Scotland's ratings use the FHIS scheme (Pass/Improvement Required) "
        "with no 0–5 scores, so they are not directly comparable with "
        "England, Wales and Northern Ireland.",
        html,
    )

    # "vs UK total" line (both legacy shapes)
    if total_uk:
        html = re.sub(
            r"(<strong>vs UK total:</strong> )(?:[^<]*?accounts for )[\d.]+(% of the )[\d,]+( Thai food businesses across the UK\.)",
            lambda m: (m.group(1)
                       + f"{city} accounts for {count / total_uk * 100:.1f}% of the "
                       + f"{total_uk:,}" + m.group(3)),
            html,
        )
        html = re.sub(
            r"(<strong>vs UK total:</strong> )(?![^<]*accounts for)[^<]*?( across the UK\.)",
            lambda m: (m.group(1)
                       + f"{city}'s {count} Thai "
                       + ("business is" if count == 1 else "businesses are")
                       + f" part of {total_uk:,}" + m.group(2)),
            html,
        )

    # ── 6. Legacy "Market Snapshot" grid + comparison cells (written by older
    # one-off generators; refreshed here so values never drift or contradict) ──
    ctx = ctx or {}
    scheme = stats.get("scheme", "FHRS")

    if scheme == "FHIS":
        avg_val = f'{stats.get("fhis_pass", 0)} of {count} Pass (FHIS)'
    else:
        legacy_stars = "★" * round(avg_rating) if avg_rating >= 1 else ""
        avg_val = f"{legacy_stars} {avg_rating:.1f}/5 (FSA data)".strip()
    html = re.sub(
        r'(<strong>Avg Hygiene Rating:</strong> <span[^>]*>)[^<]*(</span>)',
        lambda m: m.group(1) + avg_val + m.group(2), html,
    )

    if total_uk:
        share_val = f"{count / total_uk * 100:.1f}% of {total_uk:,} restaurants &amp; takeaways"
        html = re.sub(
            r'(<strong>UK Share:</strong> <span[^>]*>)[^<]*(</span>)',
            lambda m: m.group(1) + share_val + m.group(2), html,
        )

    population = ctx.get("population")
    if population:
        html = re.sub(
            r'(<strong>Population:</strong> <span[^>]*>)[^<]*(</span>)',
            lambda m: m.group(1) + f"{population:,}" + m.group(2), html,
        )

    # comparison card — hygiene cell (normalises both legacy display styles)
    if scheme == "FHIS":
        comp_val = f"{round(stats.get('fhis_pass', 0) / count * 100)}% Pass" if count else "—"
        comp_sub = "FHIS · Food Standards Scotland"
        html = re.sub(
            r'(<div class="label">Hygiene Rating</div>\s*<div class="value[^"]*">)[^<]*'
            r'(</div>\s*<div class="sub">)[^<]*(</div>)',
            lambda m: m.group(1) + comp_val + m.group(2) + comp_sub + m.group(3), html,
        )
    elif ctx.get("uk_avg"):
        uk_avg_val = ctx["uk_avg"]
        comp_val = f"★{avg_rating:.1f}"
        comp_sub = f"UK avg: ★{uk_avg_val:.1f} ({avg_rating - uk_avg_val:+.1f})"
        html = re.sub(
            r'(<div class="label">Hygiene Rating</div>\s*<div class="value[^"]*">)[^<]*'
            r'(</div>\s*<div class="sub">)[^<]*(</div>)',
            lambda m: m.group(1) + comp_val + m.group(2) + comp_sub + m.group(3), html,
        )

    # comparison card — density cell
    per_100k = ctx.get("per_100k")
    uk_density = ctx.get("uk_density")
    if uk_density:
        d_val = f"{per_100k:.1f}/100k" if per_100k else "—/100k"
        d_sub = (
            f"UK avg: {uk_density:.1f}/100k ({per_100k - uk_density:+.1f})"
            if per_100k
            else f"UK avg: {uk_density:.1f}/100k (—)"
        )
        html = re.sub(
            r'(<div class="label">Per-Capita Density</div>\s*<div class="value[^"]*">)[^<]*'
            r'(</div>\s*<div class="sub">)[^<]*(</div>)',
            lambda m: m.group(1) + d_val + m.group(2) + d_sub + m.group(3), html,
        )

    # legacy garbled line: "vs UK Average: {city} {stale_total}."
    uk_per_city = ctx.get("uk_per_city")
    if uk_per_city:
        words = "business" if count == 1 else "businesses"
        html = re.sub(
            r'(<strong>vs UK Average:</strong> )[^<]*?(\.)',
            lambda m: (
                m.group(1)
                + f"{city} has {count} Thai {words} — the UK average is {uk_per_city:.0f} per city"
                + m.group(2)
            ), html,
        )

    data_updated = ctx.get("data_updated")
    if data_updated:
        html = re.sub(
            r'(Data updated: )\d{4}-\d{2}-\d{2}',
            lambda m: m.group(1) + data_updated, html,
        )

    # ── 7. Structural fixes applied on every pass (idempotent) ──
    # 7a. "High competition Competition" — double-word badge bug (76 pages).
    html = re.sub(r'\b(\w+) competition Competition\b', r'\1 competition', html)
    # 7b. Jump-to-browse anchor: listings sit below six analysis cards; give
    # mobile users a one-tap path. Injected once, guarded by the id. City
    # pages carry the sub paragraph; county pages carry an intro paragraph.
    if 'id="jump-to-browse"' not in html:
        anchor = (
            '<p style="margin-top:14px;"><a id="jump-to-browse" href="#browse" '
            'style="display:inline-block;background:#A3132B;color:#fff;padding:11px 22px;'
            'border-radius:50px;font-weight:700;text-decoration:none;">View restaurants ↓</a></p>'
        )
        target = r'(<p class="sub">.*?</p>)'
        if not re.search(target, html, flags=re.DOTALL):
            target = r'(<p class="intro">.*?</p>)'
        html = re.sub(
            target,
            lambda m: m.group(1) + anchor,
            html,
            count=1,
            flags=re.DOTALL,
        )

    return html


def build_market_snapshot_html(city: str, stats: dict[str, Any]) -> str:
    """Build the market-snapshot AUTO block — cross-links only.

    Counts, hygiene averages and the dine-in/takeaway split already appear in
    the hero sub, city-stats card, stat-row and Market Overview card. This
    card previously restated all three, a fifth repetition adding nothing.
    It now carries only the internal-link corridor.
    """
    return (
        '<div class="card">\n'
        '  <h2>Explore <em>Further</em></h2>\n'
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
            f'background:#FFFFFF;border:1px solid var(--line);'
            f'border-radius:10px;">\n'
            f'  <summary style="cursor:pointer;font-weight:600;color: var(--ink);">'
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
        return re.sub(pattern, lambda m: replacement, html, count=1, flags=re.DOTALL)

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

EMPTY_STATE_MARKER = "<!-- CITIES-EMPTY-STATE v1 -->"


def is_empty_state(html_doc: str) -> bool:
    """True when a city page is the minimal noindexed empty state."""
    return EMPTY_STATE_MARKER in html_doc


def build_empty_state_page(city: str, slug: str) -> str:
    """Minimal noindexed page for a city with no current listings.

    Deliberately small: no stale numbers, no AUTO zones. When listings
    return, the normal generator replaces this page and the noindex is gone.
    """
    name = html_escape(city)
    return f'''<!DOCTYPE html>
<html lang="en-GB">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
{EMPTY_STATE_MARKER}
<title>Thai Restaurants in {name} | ThaiData UK</title>
<meta name="robots" content="noindex, follow">
<meta name="description" content="We don't currently list Thai restaurants in {name}. Our directory is refreshed weekly from official Food Standards Agency and Food Standards Scotland data.">
<link rel="canonical" href="https://thaidata.uk/cities/{slug}">
<style>
  body {{ font-family: -apple-system, "Segoe UI", Roboto, sans-serif; margin: 0; color: #1f2937; background: #fff; }}
  main {{ max-width: 640px; margin: 0 auto; padding: 64px 24px; }}
  h1 {{ font-size: 1.6rem; margin: 0 0 16px; }}
  p {{ line-height: 1.6; color: #4b5563; }}
  a {{ color: #A3132B; }}
</style>
</head>
<body>
<main>
  <h1>Thai restaurants in {name}</h1>
  <p>We don't currently list any Thai restaurants in {name}.</p>
  <p>ThaiData UK is refreshed every week from official Food Standards Agency
  (England, Wales &amp; Northern Ireland) and Food Standards Scotland (Scotland)
  data &mdash; if a Thai restaurant registers here, its listing will appear
  automatically.</p>
  <p><a href="/cities/">Browse all UK cities</a> &nbsp;&middot;&nbsp; <a href="/">ThaiData UK home</a></p>
</main>
</body>
</html>
'''


def process_city(
    slug: str,
    city_name: str,
    registry: dict[str, Any],
    all_data: dict[str, Any],
    city_ctx: dict[str, Any] | None = None,
    prev_cities: set[str] | None = None,
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
        # Empty cities: once the emptiness is confirmed across two data
        # snapshots, write the minimal noindexed empty state (creating the
        # file if the city never had one). A single bad fetch can never
        # stub out good pages — that is what the two-snapshot check is for.
        registry_entry = registry.get("cities", {}).get(slug, {})
        confirmed_empty = prev_cities is not None and city_name not in prev_cities
        if registry_entry.get("mode") != "manual" and confirmed_empty:
            html_path = CITIES_DIR / f"{slug}.html"
            if dry_run:
                result["action"] = "would-empty-state"
            else:
                html_path.write_text(build_empty_state_page(city_name, slug))
                result["action"] = "empty-state"
        return result

    # Read existing HTML (if any)
    html_path = CITIES_DIR / f"{slug}.html"
    existing_html: str | None = None
    if html_path.exists():
        with open(html_path) as f:
            existing_html = f.read()
    # An empty-state page is not a usable base — regenerate from scratch once
    # listings return (which also drops the noindex automatically).
    if existing_html is not None and is_empty_state(existing_html):
        existing_html = None

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
    total_uk = sum(1 for r in all_data["raw"].get("restaurants", [])
                   if r.get("type") != "pub")
    london_restaurants = [r for r in by_city.get("London", [])
                          if r.get("type") != "pub"]
    stats["_london_count"] = len(london_restaurants)
    # London population for vs-London share lines (same source as city pages)
    london_pop = None
    cities_path = REPO / "api" / "v1" / "cities.json"
    if cities_path.exists():
        with open(cities_path) as f:
            for _c in json.load(f).get("cities", []):
                if _c.get("name") == "London":
                    london_pop = _c.get("population")
                    break
    stats["_london_pop"] = london_pop
    # Raw count including excluded (for city-stats div which shows FSA total)
    raw_city = [r for r in all_data["raw"].get("restaurants", [])
                if r.get("city") == city_name and r.get("type") != "pub"]
    stats["_raw_count"] = len(raw_city)
    stats["_raw_dine_in"] = sum(1 for r in raw_city if r.get("type") == "restaurant")
    stats["_raw_takeaway"] = sum(1 for r in raw_city if r.get("type") == "takeaway")

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

    html = existing_html or new_location_shell(city_name, slug)

    # Update stale hero-section numbers (pre-dates exclusion system)
    if existing_html and mode in ("programmatic", "hybrid"):
        html = update_hero_stats(html, city_name, stats, total_uk, city_ctx)

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

    # Build and validate schema HTML before injecting into the page.
    # Catches JSON serialisation failures (e.g. backslash corruption in re.sub)
    # that the earlier dict-level validation cannot see.
    schema_html = build_schema_html(schemas)
    render_errors = validate_rendered_schema(schema_html)
    if render_errors:
        result["action"] = "quarantined"
        result["errors"].extend(render_errors)
        return result

    if mode == "programmatic":
        # Replace or inject all AUTO zones
        html = inject_auto_zones(html, "schema", schema_html)
        html = inject_auto_zones(html, "market-snapshot", build_market_snapshot_html(city_name, stats))
        if stats["chains"]:
            html = inject_auto_zones(html, "chain-presence", build_chain_presence_html(city_name, stats["chains"], stats["count"]))
        if stats["postcode_areas"]:
            html = inject_auto_zones(html, "postcode-areas", build_postcode_areas_html(stats["postcode_areas"], city_name))
        html = inject_auto_zones(html, "faq", build_faq_html(schemas))

    elif mode == "hybrid":
        # Replace existing AUTO zones + inject new ones needed for enrichment
        for zone_name, zone_content_fn in [
            ("schema", lambda: schema_html),
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

    # Affiliate block (Booking.com) — inserted at the end of <main>, then
    # shell finalisation validates zone/footer ordering as usual.
    html = inject_affiliate_block(html, city_name)

    # Finalise the shell (no-op on pages without the SHELL:location-v1 signature)
    html = finish_location_shell(html)

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
    city_ctx_map = build_city_context(all_data)

    # Previous committed data — used to confirm a city is really empty (two
    # consecutive data snapshots) before replacing its page with the empty state.
    prev_cities: set[str] | None = None
    try:
        prev_raw = subprocess.run(
            ['git', 'show', 'HEAD:data/restaurants.json'],
            capture_output=True, text=True, check=True, cwd=str(REPO)).stdout
        prev_data = json.loads(prev_raw)
        # Apply the same moderation exclusions as load_restaurants() so the
        # comparison is like-for-like (a city emptied by moderation is empty).
        excluded_ids: set[int] = set()
        excl_path = REPO / "data" / "exclusions.json"
        if excl_path.exists():
            with open(excl_path) as f:
                excluded_ids = set(json.load(f).get("excluded_fsa_ids", []))
        prev_cities = {
            r.get("city", "") for r in prev_data.get("restaurants", [])
            if r.get("id") not in excluded_ids
        }
    except Exception as e:
        print(f"  ⚠️  Could not read previous data from git — empty-state check disabled ({e})")

    # Build city name → slug mapping
    name_to_slug: dict[str, str] = {}
    for city in by_city:
        name_to_slug[slugify(city)] = city

    results: list[dict[str, Any]] = []
    quarantined_count = 0
    generated_count = 0
    skipped_count = 0
    empty_state_count = 0

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
            city_ctx=city_ctx_map.get(city_name, {}),
            prev_cities=prev_cities,
            dry_run=not args.apply,
        )
        results.append(result)

        action = result["action"]
        if action == "quarantined":
            quarantined_count += 1
            print(f"  ❌ {slug} — QUARANTINED")
            for e in result.get("errors", []):
                print(f"     {e}")
        elif action == "empty-state":
            empty_state_count += 1
            print(f"  🫥 {slug} — empty-state page written")
        elif action == "would-empty-state":
            empty_state_count += 1
            print(f"  🫥 {slug} — would write empty-state page")
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
    print(f"  Summary: {generated_count} generated, {quarantined_count} quarantined, "
          f"{empty_state_count} empty-state, {skipped_count} skipped")
    print(f"{'='*50}")

    # Build manifest
    manifest = {
        "run_date": str(date.today()),
        "applied": args.apply,
        "total_cities": len(cities_to_process),
        "generated": generated_count,
        "quarantined": quarantined_count,
        "empty_state": empty_state_count,
        "skipped": skipped_count,
        "empty_state_pages": [r["slug"] for r in results if r["action"] in ("empty-state", "would-empty-state")],
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
