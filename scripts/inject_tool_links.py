#!/usr/bin/env python3
"""Put one route into /tools on every city page and every listing.

The 21 tools were reachable from the homepage and from each other, and from
nowhere else: 0 of 278 city pages and 0 of 1,434 listings linked to them. This
adds one contextual block per page, idempotent and marker-delimited, so the
generators that patch these files leave it alone.

    python3 scripts/inject_tool_links.py            # dry run
    python3 scripts/inject_tool_links.py --apply    # write
"""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CITIES = REPO / 'cities'
LISTINGS = REPO / 'r'

MARK_OPEN = '<!-- TOOL-LINKS v1 -->'
MARK_CLOSE = '<!-- /TOOL-LINKS -->'

CSS_CARD = ('border:1px solid var(--line);border-radius:14px;background:#fff;'
            'padding:20px 22px;display:flex;gap:18px;align-items:center;'
            'justify-content:space-between;flex-wrap:wrap;')
CSS_H = 'margin:0 0 4px;font-weight:700;color:var(--ink);font-size:1rem;'
CSS_P = 'margin:0;font-size:.9rem;color:var(--ink4);max-width:62ch;'
CSS_BTN = ('display:inline-block;padding:9px 15px;border-radius:999px;'
           'background:var(--c2);color:#fff;font-size:.85rem;font-weight:600;'
           'text-decoration:none;white-space:nowrap;')
CSS_BTN_ALT = ('display:inline-block;padding:9px 15px;border-radius:999px;'
               'border:1px solid var(--c2);color:var(--c2);font-size:.85rem;'
               'font-weight:600;text-decoration:none;white-space:nowrap;')


def city_block(city: str, slug: str) -> str:
    name = html.escape(city)
    return f"""{MARK_OPEN}
<div style="max-width:1100px;margin:40px auto 0;padding:0 24px;">
  <div style="{CSS_CARD}">
    <div>
      <p style="{CSS_H}">Thinking of opening a Thai restaurant in {name}?</p>
      <p style="{CSS_P}">Two free tools run on this city's data: a market entry report, and a ranking of every UK city on cost, demand and competition.</p>
    </div>
    <div style="display:flex;gap:10px;flex-wrap:wrap;">
      <a href="/tools/thai-restaurant-market-report" style="{CSS_BTN}">Market report for {name}</a>
      <a href="/tools/where-to-open-thai-restaurant-uk" style="{CSS_BTN_ALT}">Compare UK cities</a>
    </div>
  </div>
</div>
{MARK_CLOSE}"""


def listing_block() -> str:
    return f"""{MARK_OPEN}
<div style="max-width:1100px;margin:28px auto 30px;padding:0 24px;">
  <p style="font-size:.85rem;color:var(--ink4);margin:0;">
    <a href="/tools" style="color:var(--c2);font-weight:600;text-decoration:none;">Free calculators and benchmarks for Thai restaurant owners &rarr;</a>
  </p>
</div>
{MARK_CLOSE}"""


def slugify(name: str) -> str:
    s = name.lower().replace('&', 'and')
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s


def city_names() -> dict[str, str]:
    """slug -> the city name the data uses. Beats scraping the h1, which carries
    a year suffix and sometimes 'in<em>Aberdeen</em>' with no space."""
    data = json.loads((REPO / 'data' / 'restaurants.json').read_text())
    out: dict[str, str] = {}
    for r in data.get('restaurants', []):
        city = (r.get('city') or '').strip()
        if city:
            out.setdefault(slugify(city), city)
    return out


def insert_before_footer(text: str, block: str) -> str | None:
    """Insert immediately before the page's own footer, never inside it."""
    m = re.search(r'\n[ \t]*<footer[^>]*>', text)
    if not m:
        return None
    return text[:m.start()] + '\n' + block + text[m.start():]


def process(path: Path, block: str, *, already: str | None = None) -> bool:
    text = path.read_text()
    if MARK_OPEN in text:
        # refresh in place so a fix to the copy reaches pages that already have it
        pattern = re.escape(MARK_OPEN) + r'.*?' + re.escape(MARK_CLOSE)
        refreshed = re.sub(pattern, lambda m: block, text, count=1, flags=re.S)
        if refreshed == text:
            return False
        path.write_text(refreshed)
        return True
    if already and already in text:
        return False          # empty-state or noindexed stub: leave it alone
    updated = insert_before_footer(text, block)
    if updated is None:
        return False
    path.write_text(updated)
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--limit', type=int, default=0, help='only the first N files of each type')
    args = ap.parse_args()

    city_files = sorted(CITIES.glob('*.html'))
    listing_files = sorted(LISTINGS.glob('*/**/index.html'))
    if args.limit:
        city_files = city_files[:args.limit]
        listing_files = listing_files[:args.limit]

    names = city_names()
    city_done = listing_done = skipped = 0
    for path in city_files:
        text = path.read_text()
        if 'CITIES-EMPTY-STATE' in text:
            skipped += 1
            continue
        block = city_block(names.get(path.stem, path.stem.replace('-', ' ').title()), path.stem)
        if args.apply:
            city_done += process(path, block, already='CITIES-EMPTY-STATE')
        else:
            city_done += True

    for path in listing_files:
        if args.apply:
            listing_done += process(path, listing_block())
        else:
            listing_done += MARK_OPEN not in path.read_text()

    verb = 'wrote' if args.apply else 'would write'
    print(f'{verb}: {city_done} city pages, {listing_done} listings' + (f', {skipped} stubs skipped' if skipped else ''))


if __name__ == '__main__':
    main()
