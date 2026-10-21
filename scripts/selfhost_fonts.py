#!/usr/bin/env python3
"""Replace Google Fonts with self-hosted copies.

2,064 pages loaded fonts.googleapis.com/css2 (some twice, 239 also preconnected to
gstatic). That is a render-blocking third-party round trip on every page and the
last hotlinked-Google-Fonts dependency on the site.

The faces live in css/fonts.css (8 @font-face rules: Archivo 500-800, Inter
100-900, Instrument Serif roman + italic, latin and latin-ext each). Those are the
same files the homepage already vendored; Instrument Serif is new.

Idempotent. Dry run by default; --apply writes.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK = ('<link rel="stylesheet" href="/css/fonts.css">\n'
        '<link rel="preload" href="/assets/fonts/archivo-latin-v1.woff2" as="font" '
        'type="font/woff2" crossorigin>')
MARK = 'href="/css/fonts.css"'

GF_LINK = re.compile(r'[ \t]*<link[^>]*fonts\.googleapis\.com/css2[^>]*>\s*\n?', re.I)
GF_IMPORT = re.compile(r'[ \t]*@import\s+url\(["\']?https://fonts\.googleapis\.com[^)]*\)[^;]*;\s*\n?', re.I)
PRECONNECT = re.compile(r'[ \t]*<link[^>]*rel=["\']preconnect["\'][^>]*>\s*\n?', re.I)
PRECONNECT_R = re.compile(r'[ \t]*<link[^>]*fonts\.(?:googleapis|gstatic)\.com[^>]*>\s*\n?', re.I)
SITE_FONTS = re.compile(r'[ \t]*<style id="site-fonts">.*?</style>\s*\n?', re.S)


def transform(html: str) -> tuple[str, bool]:
    if MARK in html:
        return html, False
    original = html
    html = GF_LINK.sub('', html)
    html = GF_IMPORT.sub('', html)
    html = SITE_FONTS.sub('', html)
    for pat in (PRECONNECT_R, PRECONNECT):
        html = re.sub(pat, lambda m: '' if ('googleapis' in m.group(0) or 'gstatic' in m.group(0)) else m.group(0), html)
    if html == original:
        return original, False
    if '</head>' in html:
        html = html.replace('</head>', LINK + '\n</head>', 1)
    else:
        html = html.replace('<body>', LINK + '\n<body>', 1)
    return html, True


def main(apply_changes: bool) -> None:
    pages = [p for p in ROOT.rglob('*.html') if '.git' not in p.parts]
    changed, skipped = [], []
    for page in pages:
        text = page.read_text(errors='ignore')
        if 'fonts.google' not in text and 'site-fonts' not in text:
            continue
        new, ok = transform(text)
        if not ok:
            skipped.append(page.name)
            continue
        changed.append(page)
        if apply_changes:
            page.write_text(new)
    print(f'{"rewrote" if apply_changes else "would rewrite"} {len(changed)}  skipped {len(skipped)}')
    for s in skipped[:5]:
        print('  skip', s)
    if not apply_changes:
        print('dry run — pass --apply')


if __name__ == '__main__':
    main('--apply' in sys.argv)
