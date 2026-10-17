"""Google Maps attribution on restaurant pages (Maps ToS 3.2.3(a))."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import generate_restaurant_pages as g  # noqa: E402

RECORD = {
    "id": 1525914,
    "name": "Thai 2 Go",
    "city": "Stockton On Tees",
    "type": "takeaway",
    "address": "1 High Street",
    "postcode": "TS18 1AA",
    "hygiene_rating": 4,
    "rating_date": "2026-01-01",
    "latitude": 54.56,
    "longitude": -1.31,
    "local_authority": "Stockton-on-Tees",
}

ENRICHMENT = {
    "1525914": {
        "google_place_id": "ChIJtestplaceid",
        "phone": "01642 000000",
        "website": "https://example.com",
        "price_level": "££",
        "opening_hours": '["Monday: 12:00 – 10:00 PM"]',
        "description": "Test description",
        "rating": 4.5,
        "review_count": 100,
    }
}


def test_attribution_present_when_google_fields_render():
    html = g.generate_page(RECORD, enrichment=ENRICHMENT)
    assert "Data from Google" in html, "visible attribution required wherever Places data shows"
    assert "place_id:ChIJtestplaceid" in html, "attribution must link to the Google place"
    assert html.count("Data from Google") == 1
    # Hero contact strip badge links out too
    assert '<a class="cs-attr" href="https://www.google.com/maps/place/?q=place_id:ChIJtestplaceid"' in html


def test_no_attribution_without_enrichment():
    html = g.generate_page(RECORD, enrichment={})
    assert "Data from Google" not in html
    assert 'class="cs-attr" href=' not in html


def test_attribution_falls_back_to_search_when_no_place_id():
    enr = {"1525914": {"phone": "01642 000000", "price_level": "£"}}
    html = g.generate_page(RECORD, enrichment=enr)
    assert "Data from Google" in html
    assert "google.com/maps/search/?api=1&amp;query=" in html or "google.com/maps/search/?api=1&query=" in html
    assert "place_id:" not in html
