#!/usr/bin/env python3
"""The shared tool shell, batch 1.

Five calculators built on the same scaffold now sit in one frame: site header,
one input card, a result hierarchy, and a next step. The tool's own JavaScript
and element ids are untouched, so this guards the frame only.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOOLS = REPO / 'tools'
BATCH = [
    'thai-restaurant-break-even-calculator.html',
    'thai-menu-price-elasticity-tester.html',
    'thai-restaurant-staffing-calculator.html',
    'thai-restaurant-valuation.html',
    'delivery-profit-calculator.html',
]


def text_of(name: str) -> str:
    return (TOOLS / name).read_text(errors='ignore')


def test_batch_pages_use_the_shell():
    for name in BATCH:
        html = text_of(name)
        assert 'class="tool-shell"' in html, name
        assert 'href="/css/tool-shell.css"' in html, name
        assert '<!-- SITE-NAV -->' in html, name
        assert 'class="nav-bar"' not in html, f'{name} still has the local bar'


def test_batch_pages_have_one_next_step():
    for name in BATCH:
        html = text_of(name)
        assert html.count('class="next-step"') == 1, name
        assert 'href="/tools/' in html.split('class="next-step"')[1][:400], name


def test_no_tool_ships_a_malformed_declaration():
    """`line-height:1 font-weight:800` has no semicolon; the browser drops both."""
    bad = []
    for page in TOOLS.glob('*.html'):
        css = '\n'.join(re.findall(r'<style[^>]*>(.*?)</style>', page.read_text(errors='ignore'), re.S))
        if re.search(r'\b\d(?:\.\d+)?\s+font-weight\s*:', css):
            bad.append(page.name)
    assert not bad, bad


def test_custom_properties_are_declared_before_use():
    """--ink was used for body copy on 12 pages without ever being defined."""
    bad = []
    for page in TOOLS.glob('*.html'):
        css = '\n'.join(re.findall(r'<style[^>]*>(.*?)</style>', page.read_text(errors='ignore'), re.S))
        defined = set(re.findall(r'(--[a-z0-9-]+)\s*:', css))
        used = set(re.findall(r'var\((--[a-z0-9-]+)', css))
        missing = used - defined
        if missing:
            bad.append((page.name, sorted(missing)))
    assert not bad, bad


def test_shell_keeps_the_result_list_variant_safe():
    css = (REPO / 'css' / 'tool-shell.css').read_text()
    # the grid treatment must only apply to stat strips, not to label/value lists
    assert '.tool-shell .breakdown:has(.bd-item)' in css
    assert '.tool-shell .break-row' in css
