#!/usr/bin/env python3
"""Move the restaurant directory above the market analysis on the standard city shells.

Pilot proved the layout on Leeds (first restaurant y=7405 -> y=713 at 390x844).
This applies the same move mechanically and refuses any page where the result would
lose or duplicate content.

Dry run by default; pass --apply to write.
"""
from __future__ import annotations

import html as htmllib
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CITIES = REPO / 'cities'
SLOT = '<!-- BROWSE-SLOT -->'


def find_div_end(text: str, start: int) -> int:
    """Given text[start:] beginning with '<div', return index just past its close."""
    depth = 0
    for m in re.finditer(r'<div\b|</div>', text[start:]):
        depth += 1 if m.group(0).startswith('<div') else -1
        if depth == 0:
            return start + m.end()
    raise ValueError('unbalanced div')


def cut_div(text: str, pattern: str, label: str):
    m = re.search(pattern, text, re.S)
    if not m:
        return text, None
    end = find_div_end(text, m.start())
    return text[:m.start()] + text[end:], text[m.start():end]


def cut_directory(text: str):
    m = re.search(r'<!-- BEGIN Browse Restaurants -->.*?<!-- END Browse Restaurants -->\n?', text, re.S)
    if not m:
        return text, None
    return text[:m.start()] + text[m.end():], m.group(0)


def words(text: str) -> Counter:
    """Order-insensitive fingerprint: the move reorders, it must not edit."""
    return Counter(re.findall(r'\S+', htmllib.unescape(re.sub(r'<[^>]+>', ' ', text))))


def transform(text: str):
    original = text
    text, directory = cut_directory(text)
    text, snapshot = cut_div(text, r'<div class="city-stats"[^>]*>', 'snapshot')
    text, marketpos = cut_div(text, r'<div class="card"[^>]*>\s*<h2>Market <em>Position</em>', 'marketpos')
    text, statrow = cut_div(text, r'<div class="stat-row">', 'statrow')
    if directory is None or statrow is None:
        return None, 'missing directory or stat-row'

    hero = re.search(r'<div class="hero">', text)
    if not hero:
        return None, 'no hero'
    hero_end = find_div_end(text, hero.start())

    block = '\n' + SLOT + '\n' + directory.rstrip() + '\n\n' + statrow.strip() + '\n'
    if snapshot:
        block += '\n' + snapshot.strip() + '\n'
    if marketpos:
        block += '\n' + marketpos.strip() + '\n'
    text = text[:hero_end] + block + text[hero_end:]

    # invariants
    if len(re.findall(r'<div\b', text)) != len(re.findall(r'</div>', text)):
        return None, 'div imbalance'
    if words(text) != words(original):
        return None, 'visible text changed'
    if text.count('id="browse"') != 1:
        return None, 'browse id duplicated'
    for marker in ('schema', 'market-snapshot', 'chain-presence', 'postcode-areas', 'faq'):
        if text.count(f'AUTO:{marker} ') != original.count(f'AUTO:{marker} '):
            return None, f'AUTO:{marker} count changed'
    return text, 'ok'


def main(apply: bool) -> None:
    pages = sorted(CITIES.glob('*.html'))
    done, skipped = [], []
    for page in pages:
        src = page.read_text(errors='ignore')
        if src.count('<!-- BEGIN Browse Restaurants -->') != 1 or '<div class="hero">' not in src:
            continue                      # shell/empty-state pages: different layout
        if SLOT in src:
            skipped.append((page.name, 'already moved'))
            continue
        out, status = transform(src)
        if out is None:
            skipped.append((page.name, status))
            continue
        done.append(page.name)
        if apply:
            page.write_text(out)
    print(f'moved: {len(done)}   skipped: {len(skipped)}')
    for name, why in skipped:
        print(f'  skip {name}: {why}')
    if not apply:
        print('dry run — pass --apply to write')


if __name__ == '__main__':
    main('--apply' in sys.argv)
