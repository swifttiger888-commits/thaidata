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
from head_anchor import head_end  # noqa: E402
from fix_tool_forms import first_body_level  # noqa: E402

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

# Batch 4: the last six — reports, dashboards and the two dark tools.
BATCH4 = {
    'BENCHMARKS.html': (
        'Benchmarks tell you the price. Location tells you the market.',
        '/tools/where-to-open-thai-restaurant-uk',
        'Rank the cities before you sign a lease'),
    'RESILIENCE_DASHBOARD.html': (
        'Survival is a margin question.',
        '/tools/thai-restaurant-market-report',
        'Read the market before the next renewal'),
    'WHOLESALE_BENCHMARKER.html': (
        'Now compare that against the suppliers you actually use.',
        '/tools/thai-supplier-price-tracker',
        'Check current wholesale prices by ingredient'),
    'where-to-open-thai-restaurant-uk.html': (
        'The shortlist is only half the decision.',
        '/tools/thai-restaurant-market-report',
        'Model the market for your chosen city'),
    'PROFIT_MARGIN_DEFENDER.html': (
        'Fixed costs do not move. Covers do.',
        '/tools/thai-restaurant-break-even-calculator',
        'Work out the covers you need each day'),
    'VISA_ASSISTANT.html': (
        'A sponsored chef changes your wage bill.',
        '/tools/thai-restaurant-staffing-calculator',
        'Price the rota with the new salary in it'),
}

# Batch 2: the lookup and report tools. Same frame, no result-template changes.
BATCH2 = {
    'thai-restaurant-hygiene-lookup.html': (
        'Found your rating?',
        '/claim/',
        'Claim your listing and keep it accurate'),
    'thai-competitor-radar.html': (
        'See the whole market, not just the competition.',
        '/tools/thai-restaurant-market-report',
        'Run a full market entry report for the city'),
    'thai-restaurant-market-report.html': (
        'Now compare the cities on cost and demand.',
        '/tools/where-to-open-thai-restaurant-uk',
        'Rank every city against your priorities'),
    'thai-restaurant-health-check.html': (
        'Gaps cost money quietly.',
        '/tools/thai-restaurant-break-even-calculator',
        'See what they mean in covers per day'),
    'NAP_CHECKER.html': (
        'Inconsistent details lose you customers.',
        '/claim/',
        'Claim your listing and fix it at the source'),
}

# Batch 3: generators and price trackers.
BATCH3 = {
    'MENU_SCHEMA_GENERATOR.html': (
        'Schema is half the job — crawlers still have to reach it.',
        '/tools/AI_AUDITOR',
        'Check whether AI assistants can read your menu'),
    'MENU_REVIEWER.html': (
        'Better dish copy deserves the markup to match.',
        '/tools/MENU_SCHEMA_GENERATOR',
        'Generate the menu schema for your page'),
    'AI_AUDITOR.html': (
        'Fix the markup once your menu is readable.',
        '/tools/MENU_SCHEMA_GENERATOR',
        'Generate schema the crawlers can parse'),
    'thai-ingredient-price-tracker.html': (
        'Compare what you pay against the trade price.',
        '/tools/WHOLESALE_BENCHMARKER',
        'Benchmark your supplier against the region'),
    'thai-supplier-price-tracker.html': (
        'Now check the region, not just your own invoices.',
        '/tools/WHOLESALE_BENCHMARKER',
        'See how your prices compare locally'),
}


def add_link(text: str) -> str:
    end = head_end(text)
    if end < 0:
        # no </head>: the head runs up to the first body-level element
        end = first_body_level(text, text.lower().find('<head'))
    if end > 0 and LINK in text[:end]:
        return text
    anchor = '<link rel="stylesheet" href="/css/tool-forms.css">'
    if end > 0 and anchor in text[:end]:
        i = text.find(anchor) + len(anchor)
        return text[:i] + '\n' + LINK + text[i:]
    if end > 0:
        return text[:end] + LINK + '\n' + text[end:]
    return text


def swap_nav(text: str) -> str:
    if '<!-- SITE-NAV -->' in text:
        return text
    m = re.search(r'<nav[^>]*>.*?</nav>', text, re.S | re.I)
    if not m:
        return text
    block = NAV + NAV_CSS + NAV_SCRIPT
    return text[:m.start()] + block + text[m.end():]


# The city-page nav carries two links; the tools hub carries the full site
# set. Tool pages showing a different header from the hub they were reached
# from reads as leaving the site.
SITE_LINKS = (
    '<li><a href="/guides">Guides</a></li>\n'
    '                <li><a href="/recipes/">Recipes</a></li>\n'
    '                <li><a href="/restaurants">Restaurants</a></li>\n'
    '                <li><a href="/claim/">Claim Listing</a></li>\n'
    '                <li><a href="/dish-prices">Dish prices</a></li>\n'
    '                <li><a href="/glossary">Glossary</a></li>\n'
    '                <li><a href="/thai-festivals-uk">Festivals</a></li>\n'
    '                <li><a href="/faq">FAQ</a></li>'
)


def site_links(text: str) -> str:
    m = re.search(r'(<ul class="nav-links" id="navLinks">)(.*?)(</ul>)', text, re.S)
    if not m or 'href="/guides"' in m.group(2):
        return text
    return text[:m.start(2)] + '\n                ' + SITE_LINKS + '\n            ' + text[m.end(2):]


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
    footer = text.find('<footer')
    if footer != -1:
        i = text.rfind('</div>', 0, footer)
        if i > 0:
            return text[:i] + block + text[i:]
    # No footer on the dark and generator tools. Inserting at the last </div>
    # in the file put the block inside a JavaScript template literal, where it
    # rendered once per result row. Anchor on </body> instead, and wrap it so
    # it keeps the container width.
    body = text.rfind('</body>')
    if body < 0:
        return text
    wrapped = (
        '\n    <div class="container" style="padding-top:0; padding-bottom:48px;">'
        + block
        + '    </div>\n'
    )
    return text[:body] + wrapped + text[body:]


def main(apply_changes: bool) -> None:
    touched = 0
    for name, (prompt, href, label) in {**BATCH, **BATCH2, **BATCH3, **BATCH4}.items():
        page = ROOT / 'tools' / name
        original = page.read_text()
        text = original
        text = add_link(text)
        text = body_shell(text)
        text = swap_nav(text)
        text = site_links(text)
        text = repair_css(text)
        text = next_step(text, prompt, href, label)
        if text != original:
            touched += 1
            if apply_changes:
                page.write_text(text)
    total = len(BATCH) + len(BATCH2) + len(BATCH3) + len(BATCH4)
    print(f'{"rewrote" if apply_changes else "would rewrite"} {touched} of {total} pages')
    if not apply_changes:
        print('dry run — pass --apply')


if __name__ == '__main__':
    main('--apply' in sys.argv)
