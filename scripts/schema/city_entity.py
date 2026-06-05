"""Build City schema (Wikidata-linked entity)."""
from __future__ import annotations

from typing import Any

# Wikidata Q-IDs for known cities (can grow over time)
WIKIDATA: dict[str, str | None] = {
    "london": "Q84",
    "manchester": "Q18125",
    "leeds": "Q39121",
    "birmingham": "Q65",
    "edinburgh": "Q180188",
    "bristol": "Q188811",
    "bournemouth": "Q170877",
    "york": "Q28934",
    "leicester": "Q128046",
    "milton keynes": "Q649911",
    "sheffield": "Q42448",
    "brighton": "Q163648",
    "newcastle": "Q49108",
    "oxford": "Q34217",
    "bradford": "Q167907",
    "swansea": "Q23051",
    "bath": "Q22889",
    "cornwall": "Q23148",
    "liverpool": "Q24826",
    "nottingham": "Q41262",
    "cambridge": "Q350",
    "glasgow": "Q4093",
    "cardiff": "Q10690",
    "portsmouth": "Q722513",
    "southampton": "Q79848",
    "coventry": "Q6225",
    "hull": "Q1281281",
    "derby": "Q43475",
    "stoke-on-trent": "Q134902",
    "wolverhampton": "Q134989",
    "belgian waffle": None,  # not a real city but appears in data
}


def build_city_entity(city: str, city_slug: str) -> dict[str, Any] | None:
    """Build a City schema entity with Wikidata sameAs link.

    Returns None if no Wikidata entry exists for this city.

    Args:
        city: City name (e.g. "Manchester").
        city_slug: URL slug (e.g. "manchester").

    Returns:
        City schema dict, or None.
    """
    qid = WIKIDATA.get(city_slug.lower())
    if not qid:
        return None

    return {
        "@context": "https://schema.org",
        "@type": "City",
        "name": city,
        "sameAs": f"https://www.wikidata.org/wiki/{qid}",
    }
