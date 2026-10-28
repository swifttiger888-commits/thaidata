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


# ── Directions link ──────────────────────────────────────────────────────────
# An unclaimed listing has no phone, website or hours (Places enrichment removed for
# ToS reasons), so before this the hero's only link was "Claim it free" — aimed at the
# owner. A visitor had nothing to click. The directions link is built from the FSA
# address we already hold, so it is not Places content and needs no API key.

DIRECTIONS = 'https://www.google.com/maps/search/?api=1&amp;query='


def _contact_strip(html: str) -> str:
    m = re.search(r'<div class="contact-strip".*?</div>', html, re.S)
    return m.group(0) if m else ''


def test_unclaimed_pages_offer_a_directions_link():
    missing = [str(p.relative_to(REPO)) for p in LISTINGS
               if DIRECTIONS not in _contact_strip(p.read_text(encoding='utf-8', errors='ignore'))]
    # Claimed pages get the strip removed at serve time, but it is still generated.
    assert len(missing) < len(LISTINGS) * 0.02, missing[:10]


def test_directions_query_carries_the_postcode():
    import urllib.parse
    bad = []
    for p in LISTINGS[:400]:
        strip = _contact_strip(p.read_text(encoding='utf-8', errors='ignore'))
        m = re.search(r'query=([^"&]+)', strip)
        if not m:
            continue
        q = urllib.parse.unquote(m.group(1))
        if not re.search(r'[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}|^nd$', q) and 'UK' not in q:
            bad.append((str(p.relative_to(REPO)), q))
    assert not bad, bad[:5]


def test_directions_query_does_not_repeat_the_business_name():
    # 73 FSA addresses lead with the business name ("Talay Thai Ltd, Mount Pleasant
    # Road, …"); the name is already the first element, so that segment is dropped.
    talay = REPO / 'r' / 'cornwall' / 'talay-thai' / 'index.html'
    if not talay.exists():
        return
    strip = _contact_strip(talay.read_text(encoding='utf-8'))
    import urllib.parse
    q = urllib.parse.unquote(re.search(r'query=([^"&]+)', strip).group(1))
    assert q.count('Talay Thai') == 1, q
    assert 'Mount Pleasant Road' in q


def test_directions_link_is_a_safe_external_link():
    strip = _contact_strip(LISTINGS[0].read_text(encoding='utf-8', errors='ignore'))
    assert 'target="_blank"' in strip and 'rel="noopener"' in strip


def test_middleware_still_strips_the_strip_on_claimed_pages():
    mw = (REPO / 'functions' / 'r' / '_middleware.js').read_text(encoding='utf-8')
    assert 'contact-strip' in mw
