#!/usr/bin/env python3
"""Static checks for the Phase 1 owner-help layer on generated /r/ pages.

Run: python3 -m pytest tests/test_owner_help_static.py -v
"""
import os
import re

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
OPEN_PAGE = os.path.join(REPO, 'r', 'leeds', 'my-thai', 'index.html')
CLOSED_PAGE = os.path.join(REPO, 'r', 'leeds', 'thai-edge', 'index.html')


def read(path):
    assert os.path.exists(path), f'missing sample page: {path}'
    with open(path, encoding='utf-8') as f:
        return f.read()


def test_open_page_claim_links_have_context():
    html = read(OPEN_PAGE)
    assert 'src=restaurant-card' in html
    assert 'src=hero-claim' in html
    assert '/claim/?restaurant=My%20Thai&amp;city=Leeds&amp;fsa_id=' in html


def test_open_page_report_card_present():
    html = read(OPEN_PAGE)
    assert 'id="report-card"' in html
    assert 'id="report-form"' in html
    assert 'id="report-category"' in html
    assert 'name="website" class="hp-field"' in html


def test_open_page_claim_card_faq():
    html = read(OPEN_PAGE)
    assert 'Is it free?' in html
    assert 'How long does approval take?' in html


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
