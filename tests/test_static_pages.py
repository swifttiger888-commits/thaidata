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
