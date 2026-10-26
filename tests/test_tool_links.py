#!/usr/bin/env python3
"""Every city page and every listing routes once into /tools."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CITIES = REPO / 'cities'
LISTINGS = REPO / 'r'
OPEN = '<!-- TOOL-LINKS v1 -->'


def test_city_pages_link_to_the_tools():
    missing = []
    for page in CITIES.glob('*.html'):
        text = page.read_text(errors='ignore')
        if 'CITIES-EMPTY-STATE' in text:
            continue
        if OPEN not in text or 'href="/tools/' not in text:
            missing.append(page.name)
    assert not missing, missing[:10]


def test_every_listing_links_to_the_tools():
    missing = []
    for page in LISTINGS.glob('*/**/index.html'):
        text = page.read_text(errors='ignore')
        if OPEN not in text or 'href="/tools"' not in text:
            missing.append(str(page.relative_to(REPO)))
    assert not missing, missing[:10]


def test_the_block_sits_above_the_footer_and_appears_once():
    bad = []
    sample = list(CITIES.glob('*.html'))[:20] + list(LISTINGS.glob('*/**/index.html'))[:20]
    for page in sample:
        text = page.read_text(errors='ignore')
        if 'CITIES-EMPTY-STATE' in text or '<footer' not in text:
            continue          # noindexed stub: no footer, no block
        if text.count(OPEN) != 1:
            bad.append((page.name, 'count'))
            continue
        footer = text.find('<footer')
        if footer > 0 and text.find(OPEN) > footer:
            bad.append((page.name, 'below footer'))
    assert not bad, bad


def test_city_block_names_the_city():
    """The h1 carries a year and sometimes no space before the name."""
    london = (CITIES / 'london.html').read_text()
    assert 'Thai restaurant in London?' in london
    aberdeen = (CITIES / 'aberdeen.html').read_text()
    assert 'Thai restaurant in Aberdeen?' in aberdeen


def test_listing_template_carries_the_block():
    """Listings are regenerated from templates/restaurant.html; an injected block
    that lives only in the output files disappears on the next data refresh."""
    template = (REPO / 'templates' / 'restaurant.html').read_text()
    assert OPEN in template
    assert 'href="/tools"' in template


def test_menu_template_carries_the_block():
    """Menu pages are rebuilt from scripts/build_menu_page.py, which had no block:
    rebuilding the 166 menu pages on 2026-10-26 stripped every injected block and
    re-added Google Fonts. The template, not just the output, must carry both."""
    template = (REPO / 'scripts' / 'build_menu_page.py').read_text()
    assert OPEN in template
    assert 'href="/tools"' in template
    assert 'fonts.googleapis.com' not in template
    assert 'href="/css/fonts.css"' in template
