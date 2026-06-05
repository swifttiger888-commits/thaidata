"""Build Restaurant ItemList schema from city restaurant data.

Output schema.org/ItemList containing Restaurant entries.
Does NOT use AggregateRating — FSA scores are single inspections,
not user-review aggregates. Uses additionalProperty instead.
"""
from __future__ import annotations

import re
from typing import Any


def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s)
    return s.strip("-")


def _clean_name(name: str) -> str:
    """Normalize a restaurant name: strip and collapse whitespace."""
    return " ".join(name.split())


def build_restaurant_list(
    city: str,
    restaurants: list[dict[str, Any]],
    max_items: int = 10,
    base_url: str = "https://thaidata.uk",
) -> dict[str, Any]:
    """Build an ItemList of Restaurant entries.

    Args:
        city: City name (e.g. "Manchester").
        restaurants: Sorted list of restaurant dicts from restaurants.json.
        max_items: Max entries to include (default 10).
        base_url: Site base URL for constructing /r/ links.

    Returns:
        A dict representing the schema.org ItemList, ready for json.dumps.
    """
    items: list[dict[str, Any]] = []
    for i, r in enumerate(restaurants[:max_items], 1):
        r_slug = slugify(r.get("name", ""))
        city_slug = slugify(r.get("city", ""))
        restaurant_url = f"{base_url}/r/{city_slug}/{r_slug}/"

        rating_val = r.get("hygiene_rating", "")
        # Parse rating: "5" → 5, handle non-numeric
        try:
            rating_num = int(rating_val)
        except (ValueError, TypeError):
            rating_num = None

        entry: dict[str, Any] = {
            "@type": "ListItem",
            "position": i,
            "item": {
                "@type": "Restaurant",
                "name": _clean_name(r.get("name", "")),
                "url": restaurant_url,
                "servesCuisine": "Thai",
                "address": {
                    "@type": "PostalAddress",
                    "addressLocality": r.get("city", ""),
                    "postalCode": r.get("postcode", ""),
                    "streetAddress": r.get("address", ""),
                },
            },
        }

        # Embed FSA hygiene score as additionalProperty (NOT AggregateRating)
        # FSA scores are single official inspections, not user-review aggregates.
        if rating_num is not None:
            entry["item"]["additionalProperty"] = {
                "@type": "PropertyValue",
                "name": "FSA Hygiene Rating",
                "value": str(rating_num),
            }

        items.append(entry)

    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": f"Top Thai Restaurants in {city}",
        "itemListElement": items,
    }
