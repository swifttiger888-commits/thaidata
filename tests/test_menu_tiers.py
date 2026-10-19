"""Per-section protein tiers in generated menu pages (Oct 2026).

Why this file exists: Thai menus commonly price a whole SECTION by protein
("any curry with chicken or beef £10.50") and four sections can carry four
different price lists. A single global tier table cannot express that — it
rendered one table under "Main Courses" only, so three sections published as
pricelists with no prices and read as broken.

These tests pin the per-section behaviour:
  - the tier table renders inside the section that owns it, and nowhere else,
  - dishes in a tier section legitimately carry no price,
  - JSON-LD stays valid and unpriced dishes emit no Offer,
  - ranged prices never collapse into a concatenated number ("13.0015.00").
"""
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

import build_menu_page as bmp  # noqa: E402


def _data():
    return {
        "restaurant": "Tier Test Thai",
        "city": "Testville",
        "fsa_id": "999001",
        "address": "1 Test Road, Testville",
        "source": "https://example.com/menu",
        "source_label": "the restaurant's own menu page",
        "checked": "2026-10-19",
        "categories": {
            "Curries": [
                {"name": "Green Curry", "description": "Coconut, basil", "price": None},
                {"name": "Massaman", "description": "Potato, peanut", "price": None},
            ],
            "Sides": [
                {"name": "Steamed Rice", "description": "", "price": "£3.50"},
            ],
        },
        "category_tiers": {
            "Curries": [["Chicken or Beef", "£10.50"], ["Duck", "£11.50"]],
        },
        "pricing_notes": ["Prices are for the dish with your chosen protein."],
    }


def _section(html, cid):
    m = re.search(rf'<section class="cat" id="cat-{cid}">(.*?)</section>', html, re.S)
    assert m, f"section {cid} missing"
    return m.group(1)


def test_tier_table_renders_in_owning_section_only():
    html = bmp.build(_data())
    curries = _section(html, "curries")
    sides = _section(html, "sides")
    assert "Choose your protein" in curries
    assert "£10.50" in curries and "£11.50" in curries
    assert "Choose your protein" not in sides
    assert "£3.50" in sides


def test_tier_dishes_carry_no_per_dish_price():
    html = bmp.build(_data())
    curries = _section(html, "curries")
    assert "Green Curry" in curries and "Massaman" in curries
    # no dish-price span inside the tier section: the section is priced by protein
    assert 'class="dish-price"' not in curries
    assert 'class="dish-price"' in _section(html, "sides")


def test_json_ld_valid_and_unpriced_items_have_no_offer():
    html = bmp.build(_data())
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    menus = [json.loads(b) for b in blocks if json.loads(b).get("@type") == "Menu"]
    assert len(menus) == 1
    items = [i for s in menus[0]["hasMenuSection"] for i in s.get("hasMenuItem", [])]
    by_name = {i["name"]: i for i in items}
    assert "offers" not in by_name["Green Curry"]
    assert by_name["Steamed Rice"]["offers"]["price"] == "3.50"


def test_ranged_price_emits_price_specification():
    data = _data()
    data["categories"]["Sides"] = [
        {"name": "Set Menu", "description": "", "price": "£13.00–£15.00"},
    ]
    html = bmp.build(data)
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    menus = [json.loads(b) for b in blocks if json.loads(b).get("@type") == "Menu"]
    items = [i for s in menus[0]["hasMenuSection"] for i in s.get("hasMenuItem", [])]
    offer = [i for i in items if i["name"] == "Set Menu"][0]["offers"]
    assert offer["priceSpecification"]["minPrice"] == "13.00"
    assert offer["priceSpecification"]["maxPrice"] == "15.00"
    assert "price" not in offer
    assert not re.search(r'"price":\s*"\d+\.\d{2}\d', html)
