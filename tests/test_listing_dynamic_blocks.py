#!/usr/bin/env python3
"""Guard the listing template's DYNAMIC blocks against silent anchor drift.

The icon migration changed the template's markup from <i class="fas ..."> to inline
<svg class="ic">, which silently no-opped every str.replace() anchored on the old
markup. The template default shipped on 1,266 pages ("Leeds, West Yorkshire") before
anyone noticed. These tests generate real pages and assert the data won, not the
default.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'scripts'))
sys.path.insert(0, str(REPO))

import generate_restaurant_pages as G  # noqa: E402

DATA = json.loads((REPO / 'data' / 'restaurants.json').read_text())['restaurants']


def pick(predicate):
    return next((r for r in DATA if predicate(r)), None)


def render(record):
    return G.generate_page(record, set(), {}, {})


def block_text(html, class_name):
    m = re.search(rf'class="[^"]*\b{re.escape(class_name)}\b[^"]*"[^>]*>(.*?)</(?:div|span)>', html, re.S)
    assert m, f'{class_name} block missing from generated page'
    return re.sub(r'<[^>]+>', '', m.group(1)).strip()


NON_LEEDS = pick(lambda r: r['city'] not in ('Leeds',) and r['type'] == 'restaurant')
FHIS = pick(lambda r: r['type'] == 'restaurant' and str(r.get('hygiene_rating')) == 'Pass')
TAKEAWAY = pick(lambda r: r['type'] == 'takeaway')


@pytest.mark.parametrize('record', [NON_LEEDS, FHIS, TAKEAWAY], ids=lambda r: r['name'] if r else 'none')
def test_dynamic_blocks_use_record_data(record):
    assert record, 'fixture record missing from restaurants.json'
    html = render(record)

    # The template default must never survive into a generated page.
    assert 'Leeds, West Yorkshire' not in html

    # Location line carries the record's own city.
    assert block_text(html, 'hero-location') == record['city']

    # Back-link points at the record's city, not the template default.
    nav = re.search(r'<li><a href="(/cities/[^"]*)">[^<]*(?:<[^>]+>[^<]*)*?</a></li>', html)
    assert nav, 'nav back-link missing'
    assert nav.group(1) == '/cities/' + G.slugify(record['city'])

    # Related-city link matches too.
    assert f'All Thai restaurants in {record["city"]}' in html
    assert 'All Thai restaurants in Leeds' not in html or record['city'] == 'Leeds'

    # Rating badge reflects the scheme: FHIS records must never claim an FSA score.
    badge = block_text(html, 'badge-rating')
    if str(record.get('hygiene_rating')) == 'Pass':
        assert 'FHIS' in badge
        assert 'FSA' not in badge
    else:
        assert badge.startswith('FSA')
        assert str(record['hygiene_rating']) in badge

    # Type badge reflects the record type.
    type_badge = block_text(html, 'badge-type')
    expected = {'restaurant': 'Restaurant', 'takeaway': 'Takeaway', 'pub': 'Pub Kitchen'}[record['type']]
    assert type_badge == expected


def test_review_search_links_are_venue_specific():
    """Outbound review links must query each venue, never the template default."""
    from urllib.parse import quote_plus

    rec = NON_LEEDS
    assert rec
    html = render(rec)
    assert 'id="reviews"' in html, 'reviews block missing'

    # The template's example venue must never survive into a generated page.
    assert 'My+Thai+Leeds' not in html

    expected = quote_plus(rec['name'])
    google = re.search(r'href="(https://www\.google\.com/search\?q=[^"]+)"', html)
    trip = re.search(r'href="(https://www\.tripadvisor\.co\.uk/Search\?q=[^"]+)"', html)
    assert google and trip, 'review links missing'
    assert expected in google.group(1)
    assert expected in trip.group(1)
    if rec.get('postcode'):
        assert quote_plus(rec['postcode']) in google.group(1), 'query must include the postcode'
    for m in (google, trip):
        tag = html[m.start():m.start() + 250]
        assert 'nofollow' in tag and 'noopener' in tag, 'outbound links must be noopener nofollow'
