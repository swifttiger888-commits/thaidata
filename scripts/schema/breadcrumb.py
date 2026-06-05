"""Build BreadcrumbList schema."""
from __future__ import annotations

from typing import Any


def build_breadcrumb(
    items: list[tuple[str, str]],
    base_url: str = "https://thaidata.uk",
) -> dict[str, Any]:
    """Build a BreadcrumbList schema.

    Args:
        items: List of (name, relative_path) tuples for each crumb.
               First item is the home page, last is the current page.
               Example: [("Home", "/"), ("Cities", "/cities"), ("Manchester", "/cities/manchester")]
        base_url: Site base URL.

    Returns:
        BreadcrumbList schema dict.
    """
    elements: list[dict[str, Any]] = []
    for i, (name, path) in enumerate(items, 1):
        elements.append({
            "@type": "ListItem",
            "position": i,
            "name": name,
            "item": f"{base_url}{path}",
        })

    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": elements,
    }


def city_breadcrumb(city: str, city_slug: str) -> dict[str, Any]:
    """Convenience: standard city page breadcrumb."""
    return build_breadcrumb([
        ("Home", "/"),
        ("Cities", "/thai-restaurants-city-breakdown-uk"),
        (city, f"/cities/{city_slug}"),
    ])
