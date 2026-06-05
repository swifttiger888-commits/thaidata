"""Build FAQPage schema from template Q&As populated with city data."""
from __future__ import annotations

from typing import Any


def _pluralise(count: int, singular: str, plural: str | None = None) -> str:
    """Return singular or plural form based on count."""
    if count == 1:
        return singular
    return plural or f"{singular}s"


def build_faq_page(
    city: str,
    count: int,
    avg_rating: float,
    rank: int,
    min_rating: float,
    max_rating: float,
    dine_in: int,
    takeaway: int,
    top_restaurant_names: list[str],
    chains: list[str] | None = None,
) -> dict[str, Any]:
    """Build an FAQPage schema with city-specific questions.

    All Q&A content is derived from actual data — no fabricated facts.
    Every question text and answer text must also be visible on the page.

    Args:
        city: City name.
        count: Total Thai restaurants in city.
        avg_rating: Average FSA hygiene rating (e.g. 4.2).
        rank: National rank by restaurant count.
        min_rating: Minimum hygiene rating in city.
        max_rating: Maximum hygiene rating in city.
        dine_in: Number of dine-in restaurants.
        takeaway: Number of takeaways.
        top_restaurant_names: Names of top-rated restaurants.
        chains: List of chain names present in this city (or None).

    Returns:
        FAQPage schema dict.
    """
    top_list = ", ".join(top_restaurant_names[:3])

    qas: list[dict[str, Any]] = []

    # Q1: How many Thai restaurants?
    total_word = "is" if count == 1 else "are"
    qas.append({
        "@type": "Question",
        "name": f"How many Thai restaurants are in {city}?",
        "acceptedAnswer": {
            "@type": "Answer",
            "text": (
                f"There {total_word} {count} FSA-registered Thai {_pluralise(count, 'business', 'businesses')} "
                f"in {city} — {dine_in} dine-in {_pluralise(dine_in, 'restaurant', 'restaurants')} "
                f"and {takeaway} {_pluralise(takeaway, 'takeaway', 'takeaways')}."
            ),
        },
    })

    # Q2: Top rated?
    if top_restaurant_names:
        qas.append({
            "@type": "Question",
            "name": f"What is the top-rated Thai restaurant in {city}?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": (
                    f"The highest-rated Thai restaurants in {city} include {top_list}, "
                    f"all holding {int(max_rating)}/5 FSA hygiene {_pluralise(int(max_rating), 'star')}."
                ),
            },
        })

    # Q3: Average rating?
    qas.append({
        "@type": "Question",
        "name": f"What is the average FSA hygiene rating in {city}?",
        "acceptedAnswer": {
            "@type": "Answer",
            "text": (
                f"The average FSA hygiene rating across {count} Thai "
                f"{_pluralise(count, 'business', 'businesses')} in {city} is "
                f"{avg_rating:.1f}/5 {_pluralise(int(avg_rating), 'star')}."
            ),
        },
    })

    # Q4: Chain presence?
    if chains:
        chain_text = ", ".join(chains)
        qas.append({
            "@type": "Question",
            "name": f"Which Thai chains operate in {city}?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": (
                    f"Major Thai chains present in {city} include {chain_text}. "
                    f"The remaining {max(0, count - len(chains))} "
                    f"{_pluralise(max(0, count - len(chains)), 'business', 'businesses')} "
                    f"are independent restaurants and takeaways."
                ),
            },
        })

    # Q5: Dine-in vs takeaway?
    if dine_in > 0 and takeaway > 0:
        qas.append({
            "@type": "Question",
            "name": f"Are there more dine-in Thai restaurants or takeaways in {city}?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": (
                    f"There are {dine_in} dine-in {_pluralise(dine_in, 'restaurant', 'restaurants')} "
                    f"and {takeaway} {_pluralise(takeaway, 'takeaway', 'takeaways')} in {city}, "
                    f"which means {dine_in / (dine_in + takeaway) * 100:.0f}% of Thai "
                    f"{_pluralise(dine_in + takeaway, 'business', 'businesses')} "
                    f"offer dine-in service."
                ),
            },
        })

    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": qas,
    }
