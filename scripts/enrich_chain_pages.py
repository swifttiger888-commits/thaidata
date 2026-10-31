#!/usr/bin/env python3
"""Answer the queries the chain pages actually rank for.

GSC evidence (Aug-Oct 2026): 45 chain URLs served ~4,500 impressions for 13 clicks.
The queries are "is X a chain", "how many X restaurants are there", and brand+city
("rosa thai manchester") — but every page titled itself "X — UK Thai Restaurant Chain
Profile" and linked to none of its own venues.

This pass, per chain page (chains/<slug>.html):
  * title/og:title -> "{label}: {N} UK Chain Locations | ThaiData"
  * adds a missing <h1> (the pages had none)
  * syncs the "UK Locations" field-table row to the current FSA count
  * injects a linked location list (city + hygiene rating + /r/ link)
  * adds the halal honesty line where GSC shows halal queries but we hold no data

Idempotent: the location list is marker-delimited, the other edits are keyed on the
existing title/row/CSS, so re-running rewrites rather than duplicates. Run after any
manual chain-page edit. Static pages: no template, no generator (the hub generator
only writes chains/index.html).

Usage: python3 scripts/enrich_chain_pages.py [--check]
  --check  report what would change, write nothing, exit 1 if anything would change
"""
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAIN_DIR = os.path.join(REPO, 'chains')

START = '<!-- CHAIN-LOCATIONS:START -->'
CSS_MARK = '/* chain-locations */'
CHAIN_CSS = '''/* chain-locations */
.chain-answer { font-size: 1.02rem; line-height: 1.6; margin: 10px 0 18px; max-width: 70ch; }
.chain-answer a { color: var(--c1); text-decoration: underline; text-underline-offset: 3px; }
.chain-locations { list-style: none; padding: 0; margin: 12px 0 0; }
.chain-locations li.chain-locations-city { margin: 18px 0 0; }
.chain-locations li.chain-locations-city h3 { font-size: 1rem; margin: 0 0 4px; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }
.chain-locations li.chain-locations-city ul { list-style: none; padding: 0; margin: 0; }
.chain-locations li.chain-locations-city ul li { min-height: 44px; padding: 8px 0; border-bottom: 1px solid var(--line); display: flex; flex-direction: column; justify-content: center; }
.chain-locations a { color: var(--c1); text-decoration: underline; text-underline-offset: 3px; }
.chain-loc-meta { display: block; color: var(--muted); font-size: .85rem; margin-top: 2px; }
.chain-halal { margin: 16px 0 0; font-size: .92rem; line-height: 1.55; }
@media (max-width: 600px) { .chain-locations li.chain-locations-city ul li { padding: 10px 0; } }
'''
END = '<!-- CHAIN-LOCATIONS:END -->'


def norm_name(s: str) -> str:
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    s = s.lower().replace("'", '').replace('\u2019', '')
    return ' '.join(s.split())


def slugify(s: str) -> str:
    s = norm_name(s)
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    return re.sub(r'[-\s]+', '-', s).strip('-')


def rating_label(v) -> str:
    s = str(v or '').strip()
    if s in ('', 'None'):
        return 'not rated'
    if s.isdigit() and len(s) == 1:
        return f'{s}/5'
    return s


def fmt_date(iso: str) -> str:
    try:
        return date.fromisoformat(iso).strftime('%B %Y')
    except ValueError:
        return iso


def venues_for(chain, restaurants):
    keys = chain['match']
    return [r for r in restaurants if any(norm_name(r['name']).startswith(k) for k in keys)]



def hygiene_summary(venues) -> str:
    """Computed, labelled average — never a bare "5/5" when the rows show 4s."""
    from collections import Counter
    nums, other = [], Counter()
    for r in venues:
        v = str(r.get('hygiene_rating') or '').strip()
        if v.isdigit():
            nums.append(int(v))
        elif v:
            other[v] += 1
    parts = []
    if nums:
        parts.append(f'{sum(nums) / len(nums):.1f}/5 average ({len(nums)} rated)')
    for k, n in sorted(other.items()):
        if k.lower() == 'pass':
            parts.append(f'{n} pass (Scotland)')
        else:
            parts.append(f'{n} {k}')
    return '; '.join(parts) or 'not rated'


def title_for(chain, count: int) -> str:
    plural = 's' if count != 1 else ''
    if chain['kind'] == 'chain':
        return f"{chain['label']}: {count} UK Location{plural} Listed | ThaiData"
    return f"{chain['label']} Restaurants: {count} UK Location{plural} | ThaiData"


def desc_for(chain, count: int, city_count: int, checked: str) -> str:
    former = f" (formerly {chain['former']})" if chain.get('former') else ''
    kind = 'chain' if chain['kind'] == 'chain' else 'name used by independent restaurants'
    return (f"{chain['label']}{former} — {count} FSA-registered UK locations across "
            f"{city_count} cities. Hygiene ratings, city breakdown, and links to every venue "
            f"({kind}, checked {checked}).")


def location_block(chain, venues, checked: str, limit: int = 50) -> str:
    count = len(venues)
    shown = sorted(venues, key=lambda r: (r['city'], r['name']))
    truncated = count > limit
    if truncated:
        shown = shown[:40]
    from itertools import groupby
    rows = []
    for city, group in groupby(shown, key=lambda r: r['city']):
        rows.append(f'<li class="chain-locations-city"><h3>{city}</h3><ul>')
        for r in group:
            url = f"/r/{slugify(r['city'])}/{slugify(r['name'])}/"
            street, _, _ = (r.get('address') or '').partition(',')
            base = norm_name(r['name'])
            if norm_name(street).startswith(base[:12]) or base.startswith(norm_name(street)[:12]):
                street = ''
            label = r['name'] + (f' — {street.strip()}' if street.strip() else '')
            rows.append(
                f'<li><a href="{url}">{label}</a>'
                f'<span class="chain-loc-meta">{city} &middot; FSA {rating_label(r.get("hygiene_rating"))}</span></li>')
        rows.append('</ul></li>')
    more = ''
    if truncated:
        more = (f'<li class="chain-locations-more"><a href="/r/">See all {count} locations in the '
                f'restaurant directory</a></li>')
    halal = ''
    if chain.get('halal_note'):
        halal = ('\n<p class="chain-halal"><strong>Halal certification:</strong> not held in FSA '
                 'records — check the restaurant\'s own site before booking.</p>')
    return (
        f'{START}\n'
        f'<h2 id="locations">All {chain["label"]} Locations ({count})</h2>\n'
        f'<p>Every {chain["label"]} venue registered with the Food Standards Agency '
        f'({checked}), with its current hygiene rating and a link to the full listing.</p>\n'
        f'<ul class="chain-locations">\n' + '\n'.join(rows) + (('\n' + more) if more else '') + '\n</ul>'
        f'{halal}\n'
        f'{END}'
    )


def process(path, chain, restaurants, checked, check_only):
    slug = os.path.basename(path)[:-5]
    html = open(path, encoding='utf-8').read()
    original = html
    venues = venues_for(chain, restaurants)
    count = len(venues)
    cities = sorted({r['city'] for r in venues})
    title = title_for(chain, count)
    desc = desc_for(chain, count, len(cities), checked)

    # 1. canonical + og:url (trailing-slash form 308s to this one)
    canonical = f'https://thaidata.uk/chains/{slug}'
    html = re.sub(r'<link rel="canonical" href="[^"]*"',
                  f'<link rel="canonical" href="{canonical}"', html)
    html = re.sub(r'<meta property="og:url" content="[^"]*"',
                  f'<meta property="og:url" content="{canonical}"', html)

    # 2. title + og:title
    html = re.sub(r'<title>[^<]*</title>', f'<title>{title}</title>', html, count=1)
    html = re.sub(r'<meta property="og:title" content="[^"]*"',
                  f'<meta property="og:title" content="{title}"', html, count=1)

    # 3. descriptions
    html = re.sub(r'<meta name="description" content="[^"]*"',
                  f'<meta name="description" content="{desc}"', html, count=1)
    html = re.sub(r'<meta property="og:description" content="[^"]*"',
                  f'<meta property="og:description" content="{desc}"', html, count=1)

    # 4. H1 (these pages never had one) + a direct answer and jump link above the
    #    field table, so the count is the first thing a searcher reads.
    new_h1 = f'<h1>{chain["label"]}: {count} UK Location{"s" if count != 1 else ""} Listed</h1>'
    answer_p = (
        f'<p class="chain-answer">{chain["label"]} is a UK Thai restaurant '
        f'{"chain" if chain["kind"] == "chain" else "name used by independent restaurants"}. '
        f'Our directory lists {count} FSA-registered location{"s" if count != 1 else ""} '
        f'(checked {checked}); the company may operate more, and this is not a complete estate total. '
        f'<a href="#locations">Jump to locations</a>.</p>'
    )
    if '<h1' in html:
        # rewrite in place: an earlier insert-only pass left stale wording behind
        html = re.sub(r'<h1>[^<]*</h1>', new_h1, html, count=1)
        if 'class="chain-answer"' not in html:
            html = html.replace(new_h1, new_h1 + '\n  ' + answer_p, 1)
    else:
        anchor = 'class="back-link">← All Chain Profiles</a>'
        if anchor in html:
            html = html.replace(anchor, anchor + '\n  ' + new_h1 + '\n  ' + answer_p, 1)

    # 5. sync the field-table "UK Locations" row to the live FSA count. Company-reported
    # figures ("~41 as of June 2026") are replaced here because this table is ours; the
    # prose keeps the company claim with its own date.
    html = re.sub(r'<td><strong>UK Locations</strong></td><td>[^<]*</td>',
                  f'<td><strong>UK Locations</strong></td><td>{count} FSA-registered ({checked})</td>',
                  html, count=1)
    # same row shape without a closing td before the next cell
    html = re.sub(r'<td><strong>UK Locations</strong></td><td>[^<]*(?=<td>)',
                  f'<td><strong>UK Locations</strong></td><td>{count} FSA-registered ({checked})',
                  html, count=1)

    # 6. styles for the new blocks (idempotent)
    if CSS_MARK not in html and '</style>' in html:
        html = html.replace('</style>', CHAIN_CSS + '</style>', 1)

    # 7. computed hygiene row (replaces hand-written "5/5" claims that contradict the rows)
    html = re.sub(r'<td><strong>Avg Hygiene Rating</strong></td><td>[^<]*</td>',
                  lambda m: f'<td><strong>Avg Hygiene Rating</strong></td><td>{hygiene_summary(venues)}</td>',
                  html, count=1)
    html = re.sub(r'<td><strong>Hygiene Ratings?</strong></td><td>[^<]*</td>',
                  lambda m: f'<td><strong>Hygiene Ratings</strong></td><td>{hygiene_summary(venues)}</td>',
                  html, count=1)

    # 8. location list
    block = location_block(chain, venues, checked)
    if START in html and END in html:
        html = re.sub(re.escape(START) + r'.*?' + re.escape(END), block, html, flags=re.S)
    else:
        anchor = '<h2>Source URLs</h2>'
        if anchor not in html:
            return None, 'no Source URLs anchor'
        html = html.replace(anchor, block + '\n\n' + anchor, 1)

    if html == original:
        return False, 'unchanged'
    if check_only:
        return True, f'would update ({count} venues)'
    open(path, 'w', encoding='utf-8').write(html)
    return True, f'updated ({count} venue{"s" if count != 1 else ""}, {len(cities)} cit{"ies" if len(cities) != 1 else "y"})'


def main():
    check_only = '--check' in sys.argv
    data = json.load(open(os.path.join(REPO, 'data', 'restaurants.json'), encoding='utf-8'))
    restaurants = data['restaurants']
    chains = json.load(open(os.path.join(REPO, 'data', 'chains.json'), encoding='utf-8'))['chains']
    checked = fmt_date(data.get('updated', ''))

    changed = 0
    for chain in chains:
        path = os.path.join(CHAIN_DIR, f"{chain['slug']}.html")
        if not os.path.exists(path):
            print(f"SKIP {chain['slug']}: no page")
            continue
        result, msg = process(path, chain, restaurants, checked, check_only)
        if result is None:
            print(f"ERROR {chain['slug']}: {msg}")
            continue
        if result:
            changed += 1
        print(f"{chain['slug']:20s} {msg}")

    print(f"\n{'Would change' if check_only else 'Changed'} {changed} chain page(s)")
    if check_only and changed:
        sys.exit(1)


if __name__ == '__main__':
    main()
