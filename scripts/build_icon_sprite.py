#!/usr/bin/env python3
"""Build the inline-icon sprite that replaces Font Awesome.

Font Awesome shipped two things to every listing page: a 19 KB stylesheet and a
147 KB webfont, for a vocabulary of 155 icons of which 20 carry 95% of the uses.
The icons are now SVG symbols in one cached file, referenced as
``<use href="/icons.svg#i-<style>--<name>">``.

Run with --download to refresh assets/icons.svg from the Font Awesome Free package
(icons are CC BY 4.0, code MIT — attribution is kept in the sprite header).

    python3 scripts/build_icon_sprite.py --download
    python3 scripts/build_icon_sprite.py            # rebuild sprite from cached svgs

Outputs:
    data/icon_map.json    original class name -> {"style", "name"} (canonical)
    assets/icons.svg      sprite, one <symbol> per icon
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / 'assets' / 'icon-src'
SPRITE = ROOT / 'assets' / 'icons.svg'
MAP = ROOT / 'data' / 'icon_map.json'
FA_VERSION = '6.4.0'
CDN = 'https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@' + FA_VERSION + '/svgs/'

# Icons used on the site that do not exist in Font Awesome Free. They rendered as
# nothing before (a missing glyph), so each maps to the nearest free equivalent.
SUBSTITUTE = {
    'shield-check': ('solid', 'shield-halved'),
    'shield-haltered': ('solid', 'shield-halved'),   # typo for shield-halved, in two tools pages
    'sparkles': ('solid', 'wand-magic-sparkles'),
    'radar': ('solid', 'satellite-dish'),
    'skewer': ('solid', 'kitchen-set'),
    'calendar-star': ('solid', 'calendar-check'),
    'google': ('brands', 'google'),
}

ICON_TAG = re.compile(r'<i\b([^>]*)>(.*?)</i>', re.S)
CLASS_ATTR = re.compile(r'class="([^"]*)"')
STYLE_TOKENS = {'fas': 'solid', 'far': 'regular', 'fab': 'brands',
                'fa-solid': 'solid', 'fa-regular': 'regular', 'fa-brands': 'brands'}
# 'fa fa-camera' — the bare "fa" family is solid
BARE_FAMILY = {'fa': 'solid'}


def used_icons(html_files):
    """Every (style, name) pair referenced by an <i> tag, with how often."""
    counts = collections.Counter()
    for path in html_files:
        try:
            html = path.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue
        if 'fa-' not in html:
            continue
        for attrs, _inner in ICON_TAG.findall(html):
            m = CLASS_ATTR.search(attrs)
            if not m:
                continue
            tokens = m.group(1).split()
            names = [t for t in tokens if t.startswith('fa-') and t not in STYLE_TOKENS]
            if not names:
                continue
            style = next((STYLE_TOKENS[t] for t in tokens if t in STYLE_TOKENS), None)
            if style is None:
                style = next((BARE_FAMILY[t] for t in tokens if t in BARE_FAMILY), 'solid')
            counts[(style, names[0][3:])] += 1
    return counts


def aliases():
    """Font Awesome 5 names still used in the markup -> Font Awesome 6 canonical names."""
    meta = json.loads((CACHE / 'icons.json').read_text())
    amap = {name: name for name in meta}
    for name, data in meta.items():
        for old in (data.get('aliases') or {}).get('names') or []:
            amap[old] = name
    return amap


def resolve(counts, amap):
    """(style, name) -> canonical (style, name), applying aliases and substitutions."""
    out, missing = {}, []
    for (style, name), count in counts.items():
        if name in SUBSTITUTE:
            out[(style, name)] = SUBSTITUTE[name]
            continue
        canon = amap.get(name)
        if not canon:
            missing.append((style, name, count))
            continue
        out[(style, name)] = (style, canon)
    return out, missing


def fetch_svg(style, name):
    dest = CACHE / style / (name + '.svg')
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = CDN + style + '/' + name + '.svg'
    with urllib.request.urlopen(url, timeout=40) as r:
        dest.write_bytes(r.read())
    return dest


def symbol(sid, style, name):
    raw = fetch_svg(style, name).read_text(encoding='utf-8')
    view_box = re.search(r'viewBox="([^"]+)"', raw)
    if not view_box:
        raise SystemExit('no viewBox in %s/%s' % (style, name))
    # keep only the drawing; the licence comment travels in the sprite header
    inner = re.sub(r'<!--.*?-->', '', raw, flags=re.S)
    inner = re.sub(r'^.*?<svg[^>]*>', '', inner, flags=re.S)
    inner = re.sub(r'</svg>\s*$', '', inner, flags=re.S).strip()
    inner = re.sub(r'\s+', ' ', inner)
    return '<symbol id="%s" viewBox="%s">%s</symbol>' % (sid, view_box.group(1), inner)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--download', action='store_true',
                    help='fetch missing svgs (and the alias metadata) from the CDN')
    args = ap.parse_args()

    if args.download:
        CACHE.mkdir(parents=True, exist_ok=True)
        meta = CACHE / 'icons.json'
        if not meta.exists():
            url = ('https://raw.githubusercontent.com/FortAwesome/Font-Awesome/'
                   + FA_VERSION + '/metadata/icons.json')
            with urllib.request.urlopen(url, timeout=90) as r:
                meta.write_bytes(r.read())
    if not (CACHE / 'icons.json').exists():
        raise SystemExit('missing %s — run with --download once' % (CACHE / 'icons.json'))

    html_files = [p for p in ROOT.rglob('*.html')
                  if 'node_modules' not in p.parts and '.git' not in p.parts]
    counts = used_icons(html_files)
    resolved, missing = resolve(counts, aliases())
    if missing:
        print('UNRESOLVED (not in Font Awesome Free):', missing, file=sys.stderr)

    # the style must come from the canonical entry: a substituted icon can move
    # family (fa-google is a brand, fa-shield-check is solid)
    icon_map = {name: {'style': canon[0], 'name': canon[1]}
                for (style, name), canon in sorted(resolved.items())}
    if not icon_map:
        # Every page has already been converted, so the <i> scan finds nothing.
        # Never wipe a good manifest because of that: fall back to what is on disk.
        if MAP.exists():
            icon_map = json.loads(MAP.read_text())
            print('no <i> icons left to scan; reusing %d entries from %s'
                  % (len(icon_map), MAP.name))
        else:
            raise SystemExit('nothing to build: no <i> icons and no existing icon map')
    MAP.parent.mkdir(parents=True, exist_ok=True)
    MAP.write_text(json.dumps(icon_map, indent=1, sort_keys=True) + '\n')

    symbols, seen = [], set()
    pairs = {(v['style'], v['name']) for v in icon_map.values()}
    for style, name in sorted(pairs):
        sid = 'i-%s--%s' % (style, name)
        if sid in seen:
            continue
        seen.add(sid)
        symbols.append(symbol(sid, style, name))

    sprite = (
        # No display:none on the root: an external sprite referenced through <use>
        # renders nothing if the file's root is hidden. <symbol> alone never paints.
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<!-- Icons: Font Awesome Free ' + FA_VERSION + ' by @fontawesome, CC BY 4.0 '
        '(https://fontawesome.com/license/free); extracted as SVG symbols, unmodified paths. -->'
        + ''.join(symbols) + '</svg>'
    )
    SPRITE.write_text(sprite + '\n')
    print('icons used: %d  symbols: %d  sprite: %.1f KB  map: %d entries'
          % (len(counts), len(symbols), len(sprite) / 1024, len(icon_map)))


if __name__ == '__main__':
    main()
