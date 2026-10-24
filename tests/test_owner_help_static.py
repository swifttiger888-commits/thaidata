#!/usr/bin/env python3
"""Static checks for the Phase 1 owner-help layer on generated /r/ pages.

Run: python3 -m pytest tests/test_owner_help_static.py -v
"""
import os
import re

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
OPEN_PAGE = os.path.join(REPO, 'r', 'leeds', 'my-thai', 'index.html')
CLOSED_PAGE = os.path.join(REPO, 'tests', 'fixtures', 'closed_venue.html')


def read(path):
    assert os.path.exists(path), f'missing sample page: {path}'
    with open(path, encoding='utf-8') as f:
        return f.read()


def test_open_page_claim_links_have_context():
    html = read(OPEN_PAGE)
    # Single owner action: the hero CTA, prefilled with this venue.
    assert 'src=hero-claim' in html
    assert '/claim/?restaurant=My%20Thai&amp;city=Leeds&amp;fsa_id=' in html
    # The old sidebar card duplicated the CTA beside the phone/hours block.
    assert 'src=restaurant-card' not in html
    assert 'class="claim-card"' not in html


def test_open_page_report_card_present():
    html = read(OPEN_PAGE)
    assert 'id="report-card"' in html
    assert 'id="report-form"' in html
    assert 'id="report-category"' in html
    assert 'name="website" class="hp-field"' in html


def test_open_page_has_one_owner_cta():
    html = read(OPEN_PAGE)
    # Exactly one claim link in the page body (the nav's generic "Claim or list
    # your restaurant" link is separate and not venue-prefilled).
    assert html.count('src=hero-claim') == 1
    assert 'Is it free?' not in html          # sidebar FAQ removed with the card
    assert 'How long does approval take?' not in html


def test_fsa_const_matches_meta_tag():
    html = read(OPEN_PAGE)
    meta = re.search(r'<meta name="thaidata:fsa-id" content="([^"]+)">', html)
    assert meta, 'fsa-id meta tag missing'
    assert f'const RESTAURANT_FSA_ID = "{meta.group(1)}";' in html


def test_no_dynamic_markers_left():
    for page in (OPEN_PAGE, CLOSED_PAGE):
        assert 'DYNAMIC' not in read(page)


def test_closed_page_has_no_claim_or_report_card():
    html = read(CLOSED_PAGE)
    assert 'id="report-card"' not in html
    assert 'id="claim"' not in html
    assert 'Permanently Closed' in html
    assert 'closed-notice-card' in html


def test_open_page_hero_report_link():
    html = read(OPEN_PAGE)
    assert 'id="hero-report-cta"' in html
    assert 'href="#report-card"' in html


def test_closed_page_has_no_hero_report_link():
    html = read(CLOSED_PAGE)
    assert 'href="#report-card"' not in html
