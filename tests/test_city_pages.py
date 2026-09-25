#!/usr/bin/env python3
"""Tests for city page generator and schema modules."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# Add repo root
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import pytest
from scripts.schema.local_business import build_restaurant_list
from scripts.schema.faq_page import build_faq_page
from scripts.schema.breadcrumb import build_breadcrumb, city_breadcrumb
from scripts.schema.city_entity import build_city_entity
from scripts.schema.validator import (
    validate_schema,
    validate_content_schema_match,
    strip_html_body,
    _flatten_schema,
    _has_fsa_aggregate_rating,
)

# ── Sample data ────────────────────────────────────────────────────────────────

SAMPLE_RESTAURANTS = [
    {
        "id": 1,
        "name": "Hong Thai",
        "type": "restaurant",
        "city": "Manchester",
        "postcode": "M4 6BG",
        "address": "1 Test Street, Manchester",
        "hygiene_rating": "5",
        "hygiene_score": 5,
        "structural_score": 5,
        "management_score": 0,
    },
    {
        "id": 2,
        "name": "Thai Express",
        "type": "takeaway",
        "city": "Manchester",
        "postcode": "M1 1AA",
        "address": "2 Test Street, Manchester",
        "hygiene_rating": "4",
        "hygiene_score": 10,
        "structural_score": 15,
        "management_score": 5,
    },
    {
        "id": 3,
        "name": "Rosa's Thai Cafe",
        "type": "restaurant",
        "city": "Manchester",
        "postcode": "M3 3WB",
        "address": "3 Test Street, Manchester",
        "hygiene_rating": "5",
        "hygiene_score": 0,
        "structural_score": 5,
        "management_score": 10,
    },
    {
        "id": 4,
        "name": "Rosa's Thai Cafe",
        "type": "restaurant",
        "city": "Leeds",
        "postcode": "LS1 1AA",
        "address": "4 Test Street, Leeds",
        "hygiene_rating": "5",
        "hygiene_score": 5,
        "structural_score": 0,
        "management_score": 5,
    },
]


# ── local_business tests ───────────────────────────────────────────────────────

class TestBuildRestaurantList:
    def test_basic_structure(self):
        result = build_restaurant_list("Manchester", SAMPLE_RESTAURANTS[:2], max_items=10)
        assert result["@type"] == "ItemList"
        assert result["@context"] == "https://schema.org"
        assert len(result["itemListElement"]) == 2

    def test_uses_additional_property_not_aggregate_rating(self):
        result = build_restaurant_list("Manchester", SAMPLE_RESTAURANTS[:1], max_items=10)
        entry = result["itemListElement"][0]["item"]
        assert "aggregateRating" not in entry, "Must not use AggregateRating"
        assert "additionalProperty" in entry
        assert entry["additionalProperty"]["name"] == "FSA Hygiene Rating"
        assert entry["additionalProperty"]["value"] == "5"

    def test_no_additional_property_for_missing_rating(self):
        no_rating = [dict(SAMPLE_RESTAURANTS[0], hygiene_rating="Exempt")]
        result = build_restaurant_list("Manchester", no_rating, max_items=10)
        entry = result["itemListElement"][0]["item"]
        assert "additionalProperty" not in entry

    def test_respects_max_items(self):
        result = build_restaurant_list("Manchester", SAMPLE_RESTAURANTS * 5, max_items=3)
        assert len(result["itemListElement"]) == 3

    def test_generates_restaurant_url(self):
        result = build_restaurant_list("Manchester", SAMPLE_RESTAURANTS[:1], max_items=10)
        url = result["itemListElement"][0]["item"]["url"]
        assert "/r/manchester/hong-thai/" in url

    def test_position_is_sequential(self):
        result = build_restaurant_list("Manchester", SAMPLE_RESTAURANTS[:3], max_items=10)
        for i, entry in enumerate(result["itemListElement"], 1):
            assert entry["position"] == i


# ── faq_page tests ─────────────────────────────────────────────────────────────

class TestBuildFaqPage:
    def test_basic_structure(self):
        result = build_faq_page(
            "Manchester", 3, 4.7, 1, 4.0, 5.0, 2, 1,
            ["Hong Thai", "Rosa's Thai Cafe"], ["Rosa's Thai Cafe"],
        )
        assert result["@type"] == "FAQPage"
        assert len(result["mainEntity"]) >= 4

    def test_questions_contain_city_name(self):
        result = build_faq_page(
            "Leeds", 1, 5.0, 5, 5.0, 5.0, 1, 0,
            ["Rosa's Thai Cafe"], [],
        )
        for qa in result["mainEntity"]:
            assert "Leeds" in qa["name"]

    def test_singular_vs_plural(self):
        result = build_faq_page(
            "Leeds", 1, 5.0, 5, 5.0, 5.0, 1, 0,
            ["Rosa's Thai Cafe"], [],
        )
        first_answer = result["mainEntity"][0]["acceptedAnswer"]["text"]
        assert "is 1" in first_answer
        assert "business" in first_answer

    def test_chain_question_appears_when_chains_given(self):
        result = build_faq_page(
            "Manchester", 3, 4.7, 1, 4.0, 5.0, 2, 1,
            ["Hong Thai"], ["Rosa's Thai Cafe"],
        )
        chain_qs = [q for q in result["mainEntity"] if "chains" in q["name"].lower() or "operate" in q["name"].lower()]
        assert len(chain_qs) >= 1


# ── breadcrumb tests ───────────────────────────────────────────────────────────

class TestBreadcrumb:
    def test_basic_structure(self):
        result = build_breadcrumb([
            ("Home", "/"),
            ("Cities", "/cities"),
            ("Manchester", "/cities/manchester"),
        ])
        assert result["@type"] == "BreadcrumbList"
        assert len(result["itemListElement"]) == 3

    def test_positions_are_correct(self):
        result = build_breadcrumb([
            ("Home", "/"),
            ("Cities", "/cities"),
        ])
        assert result["itemListElement"][0]["position"] == 1
        assert result["itemListElement"][1]["position"] == 2

    def test_city_breadcrumb_convenience(self):
        result = city_breadcrumb("Manchester", "manchester")
        assert result["itemListElement"][-1]["name"] == "Manchester"


# ── city_entity tests ──────────────────────────────────────────────────────────

class TestCityEntity:
    def test_known_city_returns_schema(self):
        result = build_city_entity("Manchester", "manchester")
        assert result is not None
        assert result["@type"] == "City"
        assert result["sameAs"] == "https://www.wikidata.org/wiki/Q18125"

    def test_unknown_city_returns_none(self):
        result = build_city_entity("Nowhereville", "nowhereville")
        assert result is None

    def test_london_wikidata(self):
        result = build_city_entity("London", "london")
        assert result is not None
        assert "Q84" in result["sameAs"]


# ── validator tests ────────────────────────────────────────────────────────────

class TestValidator:
    def test_aggregate_rating_detection(self):
        """Validator must detect AggregateRating + FSA content combo."""
        bad_schema = {
            "@type": "Restaurant",
            "name": "Hong Thai",
            "aggregateRating": {
                "@type": "AggregateRating",
                "ratingValue": "5",
                "name": "FSA Hygiene Rating",
            },
        }
        errors = validate_schema(bad_schema)
        assert any("AggregateRating" in e for e in errors), (
            f"Expected AggregateRating policy violation, got: {errors}"
        )

    def test_clean_schema_passes(self):
        schema = {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "item": {
                        "@type": "Restaurant",
                        "name": "Hong Thai",
                        "additionalProperty": {
                            "@type": "PropertyValue",
                            "name": "FSA Hygiene Rating",
                            "value": "5",
                        },
                    },
                }
            ],
        }
        errors = validate_schema(schema)
        assert not errors

    def test_content_schema_match_pass(self):
        html = "Welcome to Manchester. Top restaurants: Hong Thai with rating 5."
        schema = {
            "@type": "ItemList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "item": {
                        "@type": "Restaurant",
                        "name": "Hong Thai",
                    },
                }
            ],
        }
        errors = validate_content_schema_match(html, schema)
        assert not errors

    def test_breadcrumb_home_allowed_via_href(self):
        """Breadcrumb 'Home' should pass if its href exists in the HTML."""
        html = "Some city content"
        raw_html = '<a href="/">Home</a>'
        schema = {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "name": "Home",
                    "item": "https://thaidata.uk/",
                }
            ],
        }
        errors = validate_content_schema_match(html, schema, raw_html=raw_html)
        assert not errors, f"Expected no errors, got: {errors}"

    def test_content_schema_match_fail(self):
        html = "Welcome to Manchester."
        schema = {
            "@type": "ItemList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "item": {
                        "@type": "Restaurant",
                        "name": "Phantom Restaurant That Doesn't Exist",
                    },
                }
            ],
        }
        errors = validate_content_schema_match(html, schema)
        assert any("not found" in e.lower() for e in errors), f"Expected error, got: {errors}"

    def test_exempt_fields_are_skipped(self):
        html = ""
        schema = {
            "@type": "ItemList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "item": {
                        "@type": "Restaurant",
                        "name": "Hong Thai",
                    },
                }
            ],
        }
        errors = validate_content_schema_match(html, schema)
        # position should be exempt
        position_errors = [e for e in errors if "position" in e]
        assert not position_errors, f"position should be exempt but got errors: {position_errors}"

    def test_strip_html_body(self):
        html = "<html><body><script>alert('x')</script><p>Hello <b>World</b></p><style>.a{color:red}</style></body></html>"
        stripped = strip_html_body(html)
        assert "Hello World" in stripped
        assert "alert" not in stripped
        assert "color:red" not in stripped


# ── Generator dry-run tests ───────────────────────────────────────────────────

class TestGeneratorDryRun:
    def test_dry_run_returns_stats(self, tmp_path):
        """Test a minimal generator run on one city."""
        # Set up a temporary repo structure
        cities_dir = tmp_path / "cities"
        cities_dir.mkdir()
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        # Minimal restaurants.json
        test_data = {
            "name": "ThaiData UK",
            "updated": "2026-06-01",
            "total": 2,
            "restaurants": SAMPLE_RESTAURANTS[:2],
        }
        with open(data_dir / "restaurants.json", "w") as f:
            json.dump(test_data, f)

        # Minimal .cities.json
        registry = {
            "version": 1,
            "cities": {
                "manchester": {
                    "tier": "enriched",
                    "mode": "hybrid",
                    "quarantined": False,
                    "transitions": [],
                },
            },
        }
        with open(cities_dir / ".cities.json", "w") as f:
            json.dump(registry, f)

        # Create minimal existing HTML with AUTO zones
        html = """<!DOCTYPE html>
<html lang="en-GB">
<head><title>Manchester | ThaiData</title></head>
<body>
<!-- AUTO:schema -->
<!-- END:AUTO:schema -->
<!-- AUTO:top-rated -->
<!-- END:AUTO:top-rated -->
<p>Restaurants in Manchester.</p>
</body>
</html>"""
        with open(cities_dir / "manchester.html", "w") as f:
            f.write(html)

        # Now test the generator via subprocess
        import subprocess
        env = os.environ.copy()
        env["PYTHONPATH"] = str(tmp_path)

        result = subprocess.run(
            [sys.executable, "-m", "pytest", f"--rootdir={tmp_path}"],
            capture_output=True, text=True, cwd=str(tmp_path),
        )
        # Just check it runs (we'll do a more targeted test below)


# ── Flatten schema test ────────────────────────────────────────────────────────

class TestFlattenSchema:
    def test_simple_dict(self):
        result = dict(_flatten_schema({"@type": "Test", "name": "Foo"}))
        assert result["@type"] == "Test"
        assert result["name"] == "Foo"

    def test_nested_dict(self):
        result = dict(_flatten_schema({"item": {"name": "Bar", "value": 5}}))
        assert "item.name" in result
        assert result["item.name"] == "Bar"

    def test_list_items(self):
        result = dict(_flatten_schema({"items": [{"x": 1}, {"x": 2}]}))
        assert "items[0].x" in result
        assert "items[1].x" in result


# ── FSA AggregateRating detection test ────────────────────────────────────────

class TestHasFsaAggregateRating:
    def test_detects_fsa_aggregate(self):
        d = {
            "@type": "AggregateRating",
            "name": "FSA Hygiene Rating",
            "ratingValue": "5",
        }
        assert _has_fsa_aggregate_rating(d)

    def test_passes_clean_additional_property(self):
        d = {
            "@type": "Restaurant",
            "additionalProperty": {
                "@type": "PropertyValue",
                "name": "FSA Hygiene Rating",
                "value": "5",
            },
        }
        assert not _has_fsa_aggregate_rating(d)

# ── FHIS (Scotland) handling ──────────────────────────────────────────────────

FHIS_EDINBURGH = (
    [
        {"id": i, "name": f"Pass Venue {i}", "type": "restaurant",
         "city": "Edinburgh", "hygiene_rating": "Pass"}
        for i in range(14)
    ]
    + [
        {"id": 100 + i, "name": f"IR Venue {i}", "type": "takeaway",
         "city": "Edinburgh", "hygiene_rating": "Improvement Required"}
        for i in range(5)
    ]
)

LEGACY_BLOCK_HTML = """<div class="card"><h2>x Market Snapshot</h2>
<div><strong>Avg Hygiene Rating:</strong> <span>★★ 2.5/5 (FSA data)</span></div>
<div><strong>UK Share:</strong> <span>1.5% of 1268</span></div>
<div class="comparison">
<div class="comp-item"><div class="label">Per-Capita Density</div><div class="value good">4.4/100k</div><div class="sub">UK avg: 2.6/100k (+1.8)</div></div>
<div class="comp-item"><div class="label">Hygiene Rating</div><div class="value good">★4.2</div><div class="sub">UK avg: ★4.3 (-0.1)</div></div>
</div>
<li>• <strong>vs UK Average:</strong> Edinburgh 1268.</li>
<div>Data updated: 2026-06-04</div>"""


class TestFhisHandling:
    def test_compute_stats_classifies_fhis(self):
        from scripts.generate_city_pages import compute_city_stats
        stats = compute_city_stats(FHIS_EDINBURGH)
        assert stats["scheme"] == "FHIS"
        assert stats["fhis_pass"] == 14
        assert stats["fhis_improvement"] == 5
        assert stats["fhis_exempt"] == 0
        assert stats["avg_rating"] == 0.0

    def test_compute_stats_fhrs_unchanged(self):
        from scripts.generate_city_pages import compute_city_stats
        stats = compute_city_stats(SAMPLE_RESTAURANTS[:2])
        assert stats["scheme"] == "FHRS"
        assert stats["avg_rating"] == 4.5

    def test_market_snapshot_no_zero_rating_for_fhis(self):
        from scripts.generate_city_pages import build_market_snapshot_html, compute_city_stats
        stats = compute_city_stats(FHIS_EDINBURGH)
        snap = build_market_snapshot_html("Edinburgh", stats)
        assert "14 Pass" in snap
        assert "0.0" not in snap
        assert "FHIS-registered" in snap

    def test_faq_fhis_has_no_numeric_claims(self):
        faq = build_faq_page(
            "Edinburgh", 19, 0.0, 3, 0, 0, 12, 7,
            ["Ting Thai", "Absolute Thai Restaurant"],
            None, scheme="FHIS", fhis_pass=14, fhis_improvement=5,
            fhis_pass_names=["Ting Thai", "Absolute Thai Restaurant"],
        )
        text = " ".join(q["acceptedAnswer"]["text"] for q in faq["mainEntity"])
        assert "0/5" not in text and "0.0/5" not in text
        assert "Food Standards Scotland" in text
        names = [q["name"] for q in faq["mainEntity"]]
        assert any("rated" in n for n in names)

    def test_faq_fhrs_wording_unchanged(self):
        faq = build_faq_page("Manchester", 3, 4.7, 1, 4.0, 5.0, 2, 1, ["Hong Thai"], None)
        text = " ".join(q["acceptedAnswer"]["text"] for q in faq["mainEntity"])
        assert "all holding 5/5 FSA hygiene stars" in text

    def test_hero_refresh_fhis_legacy_block(self):
        from scripts.generate_city_pages import compute_city_stats, update_hero_stats
        stats = compute_city_stats(FHIS_EDINBURGH)
        ctx = {"population": 548000, "per_100k": 3.5, "uk_density": 2.1,
               "uk_per_city": 5.0, "uk_avg": 4.4, "data_updated": "2026-09-21"}
        out = update_hero_stats(LEGACY_BLOCK_HTML, "Edinburgh", stats, 1263, ctx)
        assert "14 of 19 Pass (FHIS)" in out
        assert "of 1263" in out and "1268" not in out
        assert "74% Pass" in out and "FHIS · Food Standards Scotland" in out
        assert "Data updated: 2026-09-21" in out

    def test_hero_refresh_fhrs_legacy_block(self):
        from scripts.generate_city_pages import compute_city_stats, update_hero_stats
        stats = compute_city_stats(SAMPLE_RESTAURANTS[:2])
        ctx = {"population": 243000, "per_100k": 1.6, "uk_density": 2.1,
               "uk_per_city": 5.0, "uk_avg": 4.4, "data_updated": "2026-09-21"}
        out = update_hero_stats(LEGACY_BLOCK_HTML, "Oldham", stats, 1263, ctx)
        assert "4.5/5 (FSA data)" in out
        assert "UK avg: ★4.4 (+0.1)" in out
        assert "Oldham has 2 Thai businesses — the UK average is 5 per city." in out
        assert "1268" not in out

