#!/usr/bin/env python3
"""Give the calculator tools the shared shell.

Batch 1: the five tools built on the same `.container/.layout/.controls` scaffold.

What changes per page, and nothing else:
  * the local `← Tools` bar becomes the site header used by the other 1,544 pages
  * `class="tool-shell"` on <body>, so css/tool-shell.css can find the frame
  * css/tool-shell.css linked last
  * a next-step block before the footer: one link to the next question a reader has
  * three CSS repairs found by inspection: `--ink` used but never defined on 12
    pages, and `line-height:1 font-weight:800` missing its semicolon on three,
    which silently dropped both declarations.

The tool's own JavaScript is untouched: every element id and result template stays.
Dry run by default.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from apply_city_nav import CSS as NAV_CSS, NAV, SCRIPT as NAV_SCRIPT  # noqa: E402

LINK = '<link rel="stylesheet" href="/css/tool-shell.css">'

BATCH = {
    'thai-restaurant-break-even-calculator.html': (
        'Wondering what the business is worth?',
        '/tools/thai-restaurant-valuation',
        'Get a valuation range from your turnover and profit'),
    'thai-menu-price-elasticity-tester.html': (
        'Not sure you can fill the seats?',
        '/tools/thai-restaurant-break-even-calculator',
        'Work out the covers you need just to break even'),
    'thai-restaurant-staffing-calculator.html': (
        'Staffing is your biggest fixed cost.',
        '/tools/thai-restaurant-break-even-calculator',
        'See what those hours cost you in covers'),
    'thai-restaurant-valuation.html': (
        'Before you sell, check the margin.',
        '/tools/PROFIT_MARGIN_DEFENDER',
        'Test whether your menu prices survive a cost rise'),
    'delivery-profit-calculator.html': (
        'Delivery prices move demand.',
        '/tools/thai-menu-price-elasticity-tester',
        'Test what a price change does to order volume'),
}


def add_link(text: str) -> str:
    if LINK in text:
        return text
    anchor = '<link rel="stylesheet" href="/css/tool-forms.css">'
    if anchor in text:
        return text.replace(anchor, anchor + '\n' + LINK, 1)
    return text.replace('</head>', LINK + '\n</head>', 1)


def swap_nav(text: str) -> str:
    if '<!-- SITE-NAV -->' in text:
        return text
    m = re.search(r'<nav>.*?</nav>', text, re.S | re.I)
    if not m:
        return text
    block = NAV + NAV_CSS + NAV_SCRIPT
    return text[:m.start()] + block + text[m.end():]


def body_shell(text: str) -> str:
    m = re.search(r'<body([^>]*)>', text, re.I)
    if not m:
        return text
    attrs = m.group(1)
    if 'tool-shell' in attrs:
        return text
    attrs = attrs.replace('class="', 'class="tool-shell ', 1) if 'class="' in attrs else attrs + ' class="tool-shell"'
    return text[:m.start()] + '<body' + attrs + '>' + text[m.end():]


def repair_css(text: str) -> str:
    text = text.replace('line-height:1 font-weight: 800', 'line-height:1;font-weight: 800')
    text = text.replace('line-height:1.1 font-weight', 'line-height:1.1;font-weight')
    text = text.replace('margin-bottom:16px font-weight: 800', 'margin-bottom:16px;font-weight: 800')
    # --ink is used for body copy on 12 pages but never declared
    m = re.search(r':root\s*\{([^}]*)\}', text)
    if m and '--ink:' not in m.group(1):
        block = m.group(1).rstrip()
        if not block.endswith(';'):
            block += ';'
        text = text[:m.start(1)] + block + '--ink: #1A1614;' + text[m.end(1):]
    return text


def next_step(text: str, prompt: str, href: str, label: str) -> str:
    if 'class="next-step"' in text:
        return text
    block = (
        '\n        <div class="next-step">\n'
        f'            <p>{prompt}</p>\n'
        f'            <a href="{href}">{label}'
        '<svg class="ic" aria-hidden="true"><use href="#i-solid--arrow-right"></use></svg></a>\n'
        '        </div>\n'
    )
    i = text.rfind('</div>', 0, text.find('<footer'))
    if i < 0:
        return text
    return text[:i] + block + text[i:]


def main(apply_changes: bool) -> None:
    touched = 0
    for name, (prompt, href, label) in BATCH.items():
        page = ROOT / 'tools' / name
        original = page.read_text()
        text = original
        text = add_link(text)
        text = body_shell(text)
        text = swap_nav(text)
        text = repair_css(text)
        text = next_step(text, prompt, href, label)
        if text != original:
            touched += 1
            if apply_changes:
                page.write_text(text)
    print(f'{"rewrote" if apply_changes else "would rewrite"} {touched} of {len(BATCH)} pages')
    if not apply_changes:
        print('dry run — pass --apply')


if __name__ == '__main__':
    main('--apply' in sys.argv)
