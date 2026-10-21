#!/usr/bin/env python3
"""The restaurant directory must stay above the market analysis.

The pilot moved it on 226 standard shells; the shell and London pages were built
differently and are exempt. Without this guard a future regeneration (or a stray
`add_city_restaurant_links.py` run) could quietly push the list back to the footer.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CITIES = REPO / 'cities'
SLOT = '<!-- BROWSE-SLOT -->'


def pages():
    return sorted(CITIES.glob('*.html'))


def test_slotted_pages_put_the_directory_under_the_hero():
    slotted = [p for p in pages() if SLOT in p.read_text(errors='ignore')]
    assert len(slotted) > 200, f'expected the 226 standard shells, found {len(slotted)}'
    for page in slotted:
        text = page.read_text(errors='ignore')
        slot = text.index(SLOT)
        browse = text.find('<!-- BEGIN Browse Restaurants -->', slot)
        assert browse != -1, f'{page.name}: no directory after the slot'
        assert browse - slot < 200, f'{page.name}: slot and directory drifted apart'
        overview = text.find('<h2>Market <em>Overview</em>')
        if overview != -1:
            assert browse < overview, f'{page.name}: directory still below the analysis'


def test_non_slotted_pages_are_the_expected_few():
    exempt = sorted(p.name for p in pages()
                    if SLOT not in p.read_text(errors='ignore'))
    # 26 location shells (own <!-- SHELL:browse --> region), 25 empty-state stubs,
    # london.html (bespoke editorial page). Anything new here needs a look.
    assert len(exempt) == 52, exempt
    assert 'london.html' in exempt


@pytest.mark.parametrize('name', ['leeds.html', 'aberdeen.html', 'birmingham.html'])
def test_slot_is_immediately_after_the_hero(name):
    text = (CITIES / name).read_text(errors='ignore')
    assert text.count(SLOT) == 1
    assert text.index('</div>') < text.index(SLOT)      # slot precedes the content
