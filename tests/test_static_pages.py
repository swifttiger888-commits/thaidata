#!/usr/bin/env python3
"""Static checks for site-wide pages: 404 and contact.

Run: python3 -m pytest tests/test_static_pages.py -v
"""
import os

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))


def read(name):
    path = os.path.join(REPO, name)
    assert os.path.exists(path), f'missing file: {path}'
    with open(path, encoding='utf-8') as f:
        return f.read()


def test_404_page_exists_and_marked_noindex():
    html = read('404.html')
    assert 'name="robots" content="noindex"' in html or "name='robots' content='noindex'" in html
    assert 'Page not found' in html


def test_404_page_links_home():
    html = read('404.html')
    assert 'href="/restaurants"' in html
    assert 'href="/claim/"' in html
    assert 'href="/"' in html


def test_contact_page_has_faq_and_form():
    html = read('contact.html')
    assert 'id="contact-form"' in html
    assert 'id="contact-message"' in html
    assert 'id="contact-email"' in html
    assert 'name="website" class="hp-field"' in html
    assert 'href="/claim/"' in html
    assert 'href="/data-quality"' in html


def test_index_links_to_contact():
    html = read('index.html')
    # Homepage contact route: the help strip folded into the About-the-data note
    # (v3 restructure) plus the footer Contact link.
    assert 'id="about-data"' in html
    assert html.count('<a href="/contact">') >= 1
