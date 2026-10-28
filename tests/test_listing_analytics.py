#!/usr/bin/env python3
"""Listing pages are measurable, and their SERP copy doesn't lie.

Two failures this guards against, both found in the Oct 2026 conversion audit:

1.  The 1,267 listing pages called `gtag()` in the correction-form handlers but never
    loaded the GA4 tag, so every `typeof gtag === 'function'` guard silently no-opped.
    GA4 saw 66 sessions against 319 GSC clicks, and `correction_open` / `correction_submit`
    never fired at all. The template now carries the tag *and* the cookie banner — the
    banner was missing from this page family too, so analytics would have been
    consent-less.
2.  `data/title_overrides.json` advertised "Opening Times" on two Talay Thai pages that
    cannot render opening hours (unclaimed listings carry no phone/website/hours since
    the Google Places enrichment was removed for ToS reasons). The Porthleven page became
    the site's biggest impression loser: 551 impressions, 0 clicks, position 10.1.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LISTINGS = sorted(REPO.glob('r/*/*/index.html'))
TEMPLATE = REPO / 'templates' / 'restaurant.html'
GA_ID = 'G-B6RYQZX5QX'

# Copy that promises a field the page cannot render. "Menu" is deliberately absent:
# menu pages are generated from data/menus/*.json, so promising a menu is truthful.
FALSE_PROMISES = ('opening times', 'opening hours')


def _head_copy(html: str) -> str:
    """Title + meta description only — the page body legitimately contains an
    'Opening hours' option in the correction dropdown."""
    out = []
    m = re.search(r'<title>(.*?)</title>', html, re.S)
    if m:
        out.append(m.group(1))
    for m in re.finditer(r'<meta[^>]+name="(?:description|og:description)"[^>]+content="([^"]*)"', html):
        out.append(m.group(1))
    return ' '.join(out).lower()


def test_there_are_listing_pages_to_check():
    assert len(LISTINGS) > 1000, len(LISTINGS)


def test_template_carries_the_analytics_block():
    text = TEMPLATE.read_text(encoding='utf-8')
    assert GA_ID in text, 'template lost the GA4 tag — every regeneration would go dark'
    assert '/privacy-banner.js' in text, 'template lost the consent banner'
    assert 'outbound_click' in text and 'phone_tap' in text


def test_every_listing_page_carries_ga4():
    missing = [str(p.relative_to(REPO)) for p in LISTINGS
               if GA_ID not in p.read_text(encoding='utf-8', errors='ignore')]
    assert not missing, missing[:10]


def test_every_listing_page_carries_the_consent_banner():
    missing = [str(p.relative_to(REPO)) for p in LISTINGS
               if '/privacy-banner.js' not in p.read_text(encoding='utf-8', errors='ignore')]
    assert not missing, missing[:10]


def test_no_serp_copy_promises_fields_the_page_cannot_render():
    offenders = []
    for p in LISTINGS:
        text = p.read_text(encoding='utf-8', errors='ignore')
        head = _head_copy(text)
        claimed = [phrase for phrase in FALSE_PROMISES if phrase in head]
        if claimed and 'openingHours' not in text and 'Hour' not in text.split('</head>')[0]:
            offenders.append(f'{p.relative_to(REPO)}: {claimed}')
    assert not offenders, offenders[:10]


def test_claim_page_autoselects_the_venue_it_came_from():
    """36 searches -> 4 selects was the funnel's worst step. The handoff now selects
    the exact fsa_id from the query string instead of asking the owner to find
    their own restaurant in a list."""
    text = (REPO / 'claim' / 'index.html').read_text(encoding='utf-8')
    assert 'autoPick' in text
    assert "params.get('fsa_id')" in text
    assert "'claim_autoselect'" in text
