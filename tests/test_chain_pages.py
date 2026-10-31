#!/usr/bin/env python3
"""Chain page guards.

The 27 chain pages are static HTML: chains/<slug>.html is served at
/chains/<slug> (Cloudflare Pages strips .html), and /chains/<slug>/ 308s
back to it. Their canonical tags previously pointed at the trailing-slash
form, i.e. every page declared a canonical URL that redirected right back
to itself. These tests keep canonical, og:url and internal links honest.
"""
from __future__ import annotations

import glob
import json
import os
import re

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
CHAIN_PAGES = sorted(glob.glob(os.path.join(REPO, 'chains', '*.html')))


def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def test_chain_pages_found():
    assert len(CHAIN_PAGES) >= 25, 'chain pages missing from chains/'

    assert os.path.exists(os.path.join(REPO, 'chains', 'index.html'))


def test_canonical_has_no_trailing_slash():
    """A trailing slash 308s to the slashless URL, so it cannot be the canonical."""
    problems = []
    for path in CHAIN_PAGES:
        html = read(path)
        m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
        if not m:
            problems.append(f'{path}: no canonical')
            continue
        url = m.group(1)
        if url.endswith('/') and not url.endswith('/chains/'):
            problems.append(f'{path}: canonical {url} redirects to {url.rstrip("/")}')
    assert not problems, '\n'.join(problems)


def test_canonical_matches_the_served_path():
    problems = []
    for path in CHAIN_PAGES:
        slug = os.path.basename(path)[:-5]
        html = read(path)
        canonical = re.search(r'<link rel="canonical" href="([^"]+)"', html)
        og = re.search(r'<meta property="og:url" content="([^"]+)"', html)
        expected = 'https://thaidata.uk/chains/' if slug == 'index' else f'https://thaidata.uk/chains/{slug}'
        if canonical and canonical.group(1) != expected:
            problems.append(f'{path}: canonical {canonical.group(1)} != {expected}')
        if og and og.group(1) != expected:
            problems.append(f'{path}: og:url {og.group(1)} != {expected}')
    assert not problems, '\n'.join(problems)


def test_chain_pages_link_to_their_venues():
    """A chain page with no /r/ links cannot answer "where is my nearest one?"."""
    problems = []
    for path in CHAIN_PAGES:
        slug = os.path.basename(path)[:-5]
        if slug == 'index':
            continue
        html = read(path)
        if not re.search(r'href="/r/[a-z0-9-]+/[a-z0-9-]+/"', html):
            problems.append(f'{path}: no links to individual venue pages')
    assert not problems, '\n'.join(problems)


def test_titles_answer_the_count_query():
    """GSC shows "how many X restaurants" / "is X a chain" — the count must be in the title."""
    with open(os.path.join(REPO, 'data', 'restaurants.json'), encoding='utf-8') as f:
        data = json.load(f)
    with open(os.path.join(REPO, 'data', 'chains.json'), encoding='utf-8') as f:
        chains = json.load(f)['chains']
    restaurants = data['restaurants']

    def norm(s):
        import unicodedata
        s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
        return ' '.join(s.replace("'", '').replace('\u2019', '').split())

    problems = []
    for chain in chains:
        path = os.path.join(REPO, 'chains', f"{chain['slug']}.html")
        if not os.path.exists(path):
            continue
        html = read(path)
        count = sum(1 for r in restaurants if any(norm(r['name']).startswith(k) for k in chain['match']))
        title = re.search(r'<title>([^<]*)</title>', html)
        assert title, f'{path}: no title'
        title = title.group(1)
        if f'{count} UK' not in title:
            problems.append(f'{path}: title lacks the live count ({count}): {title}')
        if 'Chain Profile' in title:
            problems.append(f'{path}: boilerplate title survived: {title}')
        if len(title) > 65:
            problems.append(f'{path}: title {len(title)} chars (>65): {title}')
        if '<h1' not in html:
            problems.append(f'{path}: no <h1>')
    assert not problems, '\n'.join(problems)
