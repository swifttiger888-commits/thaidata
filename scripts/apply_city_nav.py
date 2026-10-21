#!/usr/bin/env python3
"""Give city pages the same header as listing pages.

Home keeps its fixed masthead: that header carries a page-specific CLS workaround
(pinned geometry before first paint) and is the brand landing treatment. The two
content families — 1,266 listings and 278 city pages — now share one 64px bar.

Dry run by default; --apply writes. Idempotent: pages already carrying SITE-NAV are
skipped.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CITIES = ROOT / 'cities'
MARK = '<!-- SITE-NAV -->'

NAV = MARK + '''
    <nav class="nav" id="nav"><div class="nav-inner">
            <a href="/index.html" class="logo">
                <img src="/thaidata-mark-v2.svg" alt="ThaiData" class="logo-icon" width="32" height="32">
                ThaiData
            </a>
            <button class="hamburger" onclick="toggleMenu()" aria-label="Toggle menu">
                <svg class="ic" aria-hidden="true"><use href="#i-solid--bars"></use></svg>
            </button>
            <ul class="nav-links" id="navLinks">
                <li><a href="/thai-restaurants-city-breakdown-uk">All Cities</a></li>
                <li><a href="/claim/?src=city-page">Claim or list your restaurant</a></li>
            </ul>
</div></nav>
'''

CSS = '''<style>/* SITE-NAV: shared with listing pages */
nav.nav { display: block; position: sticky; top: 0; z-index: 100; padding: 0; height: auto; background: rgba(255,255,255,0.95); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border-bottom: 1px solid var(--line); }
.nav .nav-inner { max-width: 1100px; margin: 0 auto; padding: 0 24px; height: 64px; display: flex; align-items: center; justify-content: space-between; }
.nav .logo { display: flex; align-items: center; gap: 12px; font-weight: 700; font-size: 1.35rem; color: var(--ink); text-decoration: none; letter-spacing: -0.02em; }
.nav .logo-icon { width: 32px; height: 32px; }
.nav .nav-links { display: flex; align-items: center; gap: 8px; list-style: none; margin: 0; padding: 0; }
.nav .nav-links a { color: var(--ink2); text-decoration: none; font-size: 0.875rem; font-weight: 500; padding: 8px 14px; border-radius: 999px; transition: all 0.2s; }
.nav .nav-links a:hover { color: var(--c2); background: #F7E8EB; }
.nav .hamburger { display: none; background: none; border: none; color: var(--ink); font-size: 1.5rem; cursor: pointer; padding: 6px; }
@media (max-width: 768px) {
  .nav .hamburger { display: block; }
  .nav .nav-links { display: none; position: absolute; top: 64px; left: 0; right: 0; background: white; border-bottom: 1px solid var(--line); flex-direction: column; padding: 16px; gap: 4px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); }
  .nav .nav-links.open { display: flex; }
  .nav .nav-links a { width: 100%; padding: 12px 16px; }
}</style>
'''

SCRIPT = '''<script>if (typeof toggleMenu !== 'function') { function toggleMenu() { var l = document.getElementById('navLinks'); if (l) l.classList.toggle('open'); } }</script>
'''


def apply(text: str) -> str:
    if MARK in text:
        return text
    m = re.search(r'\n?[ \t]*<nav[^>]*>.*?</nav>\n?', text, re.S)
    if not m:
        raise ValueError('no <nav> to replace')
    text = text[:m.start()] + '\n' + NAV + text[m.end():]
    # styles go at the end of the page's first <style> so they win on order
    if '</style>' in text:
        i = text.index('</style>')
        text = text[:i] + CSS.split('<style>', 1)[1].rsplit('</style>', 1)[0] + '\n' + text[i:]
    else:
        text = text.replace('</head>', CSS + '</head>', 1)
    if 'id="navLinks"' in text and 'function toggleMenu' not in text:
        text = text.replace('</body>', SCRIPT + '</body>', 1)
    return text


def main(apply_changes: bool) -> None:
    pages = sorted(CITIES.glob('*.html'))
    changed, skipped = [], []
    for page in pages:
        text = page.read_text(errors='ignore')
        if MARK in text:
            continue
        if '<nav' not in text or len(text) < 5000:      # empty-state stubs have no nav
            skipped.append(page.name)
            continue
        try:
            new = apply(text)
        except ValueError as exc:
            skipped.append(f'{page.name}: {exc}')
            continue
        changed.append(page.name)
        if apply_changes:
            page.write_text(new)
    print(f'rewrote {len(changed)}  skipped {len(skipped)}')
    for s in skipped[:10]:
        print('  skip', s)
    if not apply_changes:
        print('dry run — pass --apply')


if __name__ == '__main__':
    main('--apply' in sys.argv)
