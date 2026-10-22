#!/usr/bin/env python3
"""City pages share the listing header; home keeps its own masthead.

Home's header carries a CLS workaround (pinned geometry before first paint) and is
the brand landing treatment, so it is deliberately out of scope. The two content
families must not drift apart again.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CITIES = REPO / 'cities'
MARK = '<!-- SITE-NAV -->'


def city_pages():
    return sorted(CITIES.glob('*.html'))


def test_standard_city_pages_carry_the_shared_header():
    marked = [p for p in city_pages() if MARK in p.read_text(errors='ignore')]
    assert len(marked) > 200, f'expected ~232, found {len(marked)}'
    for page in marked:
        text = page.read_text(errors='ignore')
        assert 'class="nav-inner"' in text, page.name
        assert 'All Cities' in text, page.name
        assert 'href="/thai-restaurants-city-breakdown-uk"' in text, page.name
        assert 'class="nav-bar"' not in text, f'{page.name}: old city bar markup still present'
        # the hamburger needs its symbol in the page's own sprite
        if 'aria-label="Toggle menu"' in text:
            assert 'id="i-solid--bars"' in text, f'{page.name}: bars symbol missing'


def test_home_keeps_its_masthead():
    home = (REPO / 'index.html').read_text()
    assert 'id="main-nav"' in home
    assert MARK not in home


def test_listing_header_matches_city_header():
    listing = (REPO / 'r' / 'leeds' / 'chao-phraya-thai-restaurant' / 'index.html').read_text()
    for needle in ('class="nav-inner"', 'id="navLinks"', 'thaidata-mark-v2.b8f0bcad.svg', 'Toggle menu'):
        assert needle in listing, needle


def test_county_pages_are_wrapped_in_the_shell():
    """These 23 pages were bare fragments: no head chrome, nav, h1 or footer."""
    county = [p for p in city_pages()
              if 'CITIES-MODE: programmatic' in p.read_text(errors='ignore')
              and '<!-- SHELL:location-v1 -->' in p.read_text(errors='ignore')]
    assert len(county) >= 23, len(county)
    for page in county:
        text = page.read_text(errors='ignore')
        assert text.count('class="nav" id="nav"') == 1, page.name
        assert '<h1' in text, f'{page.name}: no h1'
        assert '<footer' in text, f'{page.name}: no footer'
        assert '<main' in text, f'{page.name}: no main landmark'
