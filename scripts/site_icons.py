#!/usr/bin/env python3
"""Replace Font Awesome <i> icons with inline SVG symbols unique to each page.

Font Awesome cost every listing page a 19 KB stylesheet plus a 147 KB webfont for
155 icons (top 20 = 95% of uses). This module rewrites the markup instead:

    <i class="fas fa-arrow-left"></i>
    ->  <svg class="ic" aria-hidden="true"><use href="#i-solid--arrow-left"></use></svg>

and injects a hidden sprite holding ONLY the symbols that page uses (a listing needs
~15, about 9 KB of markup) — no stylesheet, no webfont, no extra request.

Why inline and not one shared /icons.svg: `<use href="/icons.svg#id">` cross-document
failed to paint in headless Chrome unless the server sent CORS headers, which a static
Pages deployment does not; same-document fragment references always work and still
save the request.

Icon paths come from build_icon_sprite.py (Font Awesome Free 6.4.0, CC BY 4.0).

Use:
    from site_icons import transform
    html = transform(html)

To convert the checked-in static pages in place:
    python3 scripts/site_icons.py --all
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MAP_FILE = ROOT / 'data' / 'icon_map.json'
SPRITE = ROOT / 'assets' / 'icons.svg'

ICON_CSS = (
    '.ic{display:inline-block;width:1em;height:1em;fill:currentColor;'
    'vertical-align:-0.125em;flex-shrink:0}'
)

STYLE_TOKENS = {'fas': 'solid', 'far': 'regular', 'fab': 'brands',
                'fa-solid': 'solid', 'fa-regular': 'regular', 'fa-brands': 'brands'}
BARE_FAMILY = {'fa': 'solid'}

ICON_TAG = re.compile(r'<i\b([^>]*)>(.*?)</i>', re.S)
CLASS_ATTR = re.compile(r'\s*class="([^"]*)"')
FA_LINK = re.compile(r'[ \t]*<link[^>]*font-awesome[^>]*>\s*\n?', re.I)
SYMBOL = re.compile(r'<symbol id="([^"]+)" viewBox="([^"]+)">(.*?)</symbol>', re.S)
SPRITE_BLOCK = re.compile(r'<svg id="icon-sprite".*?</svg>', re.S)


def _load_map():
    try:
        return json.loads(MAP_FILE.read_text())
    except OSError:
        return {}


def _load_symbols():
    """id -> (viewBox, inner markup) from the built sprite."""
    try:
        text = SPRITE.read_text()
    except OSError:
        return {}
    return {sid: (vb, inner) for sid, vb, inner in SYMBOL.findall(text)}


def _attrs_without_class(attrs: str) -> str:
    attrs = CLASS_ATTR.sub('', attrs).strip()
    return (' ' + attrs) if attrs else ''


def _symbol_id(tokens):
    names = [t for t in tokens if t.startswith('fa-') and t not in STYLE_TOKENS]
    if not names:
        return None
    style = next((STYLE_TOKENS[t] for t in tokens if t in STYLE_TOKENS), None)
    if style is None:
        style = next((BARE_FAMILY[t] for t in tokens if t in BARE_FAMILY), None)
    if style is None:
        return None
    return 'i-%s--%s' % (style, names[0][3:]), names[0][3:]


def transform_icons(html: str):
    """Rewrite <i class="fa..."> tags. Returns (html, set of symbol ids used).
    Unknown icons are left untouched so the CI guard can name them."""
    icon_map = _load_map()
    used = set()

    def repl(m):
        attrs = m.group(1)
        cm = CLASS_ATTR.search(attrs)
        if not cm:
            return m.group(0)
        tokens = cm.group(1).split()
        if not any(t.startswith('fa-') for t in tokens):
            return m.group(0)          # an ordinary <i>, not an icon
        resolved = _symbol_id(tokens)
        if not resolved:
            return m.group(0)
        _fallback_sid, original = resolved
        entry = icon_map.get(original)
        if not entry:
            return m.group(0)
        sid = 'i-%s--%s' % (entry['style'], entry['name'])
        used.add(sid)
        return ('<svg class="ic" aria-hidden="true"%s><use href="#%s"></use></svg>'
                % (_attrs_without_class(attrs), sid))

    html = ICON_TAG.sub(repl, html)
    # a page that has already been through this transform keeps its <use> refs but
    # loses its sprite when regenerated — carry those ids forward so a re-run is
    # idempotent instead of silently blanking every icon.
    used.update(re.findall(r'<use href="#([^"]+)"', html))
    return html, used


def strip_stylesheet(html: str) -> str:
    return FA_LINK.sub('', html)


def inject_sprite(html: str, used, symbols) -> str:
    """Drop a hidden sprite holding just this page's icons before the first content."""
    html = SPRITE_BLOCK.sub('', html)
    if not used:
        return html
    parts = ['<symbol id="%s" viewBox="%s">%s</symbol>' % (sid, symbols[sid][0], symbols[sid][1])
             for sid in sorted(used) if sid in symbols]
    if not parts:
        return html
    block = ('<svg id="icon-sprite" xmlns="http://www.w3.org/2000/svg" style="display:none" '
             'aria-hidden="true">' + ''.join(parts) + '</svg>')
    for anchor in ('<body>', '<body '):
        idx = html.find(anchor)
        if idx != -1:
            if anchor == '<body ':
                idx = html.find('>', idx) + 1
            else:
                idx += len(anchor)
            return html[:idx] + block + html[idx:]
    return block + html


def inject_css(html: str) -> str:
    if 'class="ic"' not in html:
        return html
    if '.ic{display:inline-block;width:1em' in html:
        return html
    block = '<style>' + ICON_CSS + '</style>\n'
    # Some generated shells (city pages, tools) omit </head> entirely, so fall back
    # to the <body> tag. Without a width/height rule an inline <svg> defaults to
    # 300x150 CSS px and the icon dwarfs the text around it.
    for anchor in ('</head>', '<body>', '<body '):
        idx = html.find(anchor)
        if idx != -1:
            return html[:idx] + block + html[idx:]
    return block + html


def transform(html: str) -> str:
    symbols = _load_symbols()
    html, used = transform_icons(html)
    html = inject_sprite(strip_stylesheet(html), used, symbols)
    return inject_css(html)


def leftover_icons(html: str):
    """Icon <i> tags still present — the CI guard fails on these."""
    found = []
    for attrs, _inner in ICON_TAG.findall(html):
        cm = CLASS_ATTR.search(attrs)
        if cm and any(t.startswith('fa-') for t in cm.group(1).split()):
            found.append(cm.group(1))
    return found


def missing_symbols(html: str, symbols):
    """<use> references with no matching symbol on the page — the failure mode that
    renders an invisible gap instead of an error."""
    ids = set(re.findall(r'<use href="#([^"]+)"', html))
    present = set(re.findall(r'<symbol id="([^"]+)"', html))
    return sorted(ids - present), sorted(present - set(symbols))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--all', action='store_true', help='rewrite every checked-in *.html in place')
    ap.add_argument('--check', action='store_true', help='report pages still on Font Awesome')
    args = ap.parse_args()

    pages = [p for p in ROOT.rglob('*.html') if not ({'node_modules', '.git'} & set(p.parts))]
    if args.check:
        bad = []
        for p in pages:
            html = p.read_text(encoding='utf-8', errors='ignore')
            if 'font-awesome' in html.lower() or leftover_icons(html):
                bad.append(str(p.relative_to(ROOT)))
        print('pages still using Font Awesome: %d' % len(bad))
        for b in bad[:20]:
            print('  ' + b)
        return 1 if bad else 0

    changed = 0
    for p in pages:
        html = p.read_text(encoding='utf-8', errors='ignore')
        if 'font-awesome' not in html.lower() and not leftover_icons(html):
            continue
        new = transform(html)
        if new != html:
            p.write_text(new, encoding='utf-8')
            changed += 1
    print('rewrote %d page(s)' % changed)


if __name__ == '__main__':
    sys.exit(main() or 0)
