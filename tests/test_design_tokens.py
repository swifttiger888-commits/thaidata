#!/usr/bin/env python3
"""The design tokens in every page family must match scripts/design_tokens.py.

This does not restyle anything: it pins the values that are live today, so the next
person changing a colour edits one file. When the remaining drift is deliberately
unified (ink-mute, radii), update design_tokens.py and this test and the rendered
before/after together.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'scripts'))

import design_tokens  # noqa: E402


def root_decls(text: str) -> dict[str, str] | None:
    m = re.search(r':root\s*\{(.*?)\}', text, re.S)
    if not m:
        return None
    return {k: v.strip() for k, v in re.findall(r'(--[\w-]+)\s*:\s*([^;]+);', m.group(1))}


def resolve(decls: dict[str, str]) -> dict[str, str]:
    """Expand one level of var(--x) aliasing so formatting differences don't fail."""
    out = {}
    for name, value in decls.items():
        m = re.fullmatch(r'var\((--[\w-]+)\)', value)
        out[name] = decls.get(m.group(1), value) if m else value
    return out


def as_expected(family: str) -> dict[str, str]:
    return resolve({f'--{k}': v for k, v in design_tokens.FAMILIES[family].items()})


def test_listing_template_tokens_match_module():
    text = (REPO / 'templates' / 'restaurant.html').read_text()
    live = root_decls(text)
    assert live is not None, 'templates/restaurant.html has no :root block'
    assert resolve(live) == as_expected('listing'), (
        'templates/restaurant.html :root drifted from scripts/design_tokens.py'
    )


def test_city_pages_share_one_token_block():
    pages = sorted((REPO / 'cities').glob('*.html'))
    assert pages, 'no city pages found'
    standard = as_expected('city')
    drifted, no_root = [], []
    for page in pages:
        decls = root_decls(page.read_text(errors='ignore'))
        if decls is None:
            no_root.append(page.name)      # minimal noindex empty-state pages
            continue
        live = resolve(decls)
        expected = standard
        # Extra names (e.g. London's --card-bg, the variant's --accent) are allowed;
        # the shared names must all match.
        if any(live.get(k) != v for k, v in expected.items()):
            drifted.append(page.name)
    assert not drifted, f'{len(drifted)} city pages drifted from design_tokens.py: {drifted[:5]}'
    assert len(no_root) < len(pages), 'no city page declares the tokens at all'
