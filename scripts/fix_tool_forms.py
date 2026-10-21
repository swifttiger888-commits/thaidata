#!/usr/bin/env python3
"""Defect pass on the 21 tool pages.

Fixes, all measured on the live site before/after:
  1. Typed text invisible on 3 tools (1.0-1.6:1) and no field boundary on 2 more
     (1.02:1) -> shared /css/tool-forms.css, with body.tool-dark on the four tools
     whose fields sit on a dark panel.
  2. Nine range sliders across three tools had no visible thumb at all.
  3. 55 controls had no programmatic label: aria-label taken from the visible
     label text, with a small hand-checked override table.
  4. Buttons measured at 25-38px tall get a 40px minimum.
  5. The hub's featured NLW Wage Calculator linked to the homepage and no such
     tool exists; AI_AUDITOR.html was linked from nowhere.

Idempotent. Dry run by default.
"""
from __future__ import annotations

import html as htmllib
import json
import re
import sys
from pathlib import Path

from head_anchor import head_end

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / 'tools'
LINK = '<link rel="stylesheet" href="/css/tool-forms.css">'

DARK = {'AI_AUDITOR.html', 'WHOLESALE_BENCHMARKER.html',
        'PROFIT_MARGIN_DEFENDER.html', 'VISA_ASSISTANT.html'}

# where the automatic extraction picked up a page heading or a stale value
OVERRIDES = {
    ('AI_AUDITOR.html', 'auditorUrl'): 'Restaurant website address',
    ('thai-competitor-radar.html', 'citySelect'): 'City',
    ('thai-restaurant-market-report.html', 'citySelect'): 'City',
    ('thai-restaurant-hygiene-lookup.html', 'searchInput'): 'Restaurant name, city or postcode',
}
SKIP = {('VISA_ASSISTANT.html', 'rqfLevel')}   # already has a <label for=...>

CARD = '''            <a href="tools/AI_AUDITOR.html" class="tool-card">
                <span class="tc-icon"><svg class="ic" aria-hidden="true"><use href="#i-solid--robot"></use></svg></span>
                <div class="tc-title">AI Visibility Auditor</div>
                <div class="tc-desc">Test whether AI assistants can read your menu. Checks for PDF traps, missing schema, and crawler blocks.</div>
                <span class="tc-tag tag-data">AEO</span>
            </a>
'''


def first_body_level(text: str, start: int = 0) -> int:
    """Index of the first element that starts the body, for pages with no </head>."""
    m = re.search(r'<(?:body|header|main)\b', text[start:], re.I)
    return start + m.start() if m else -1


def add_link(text: str) -> str:
    end = head_end(text)
    if end > 0 and LINK in text[:end]:
        return text
    if end > 0:
        return text[:end] + LINK + '\n' + text[end:]
    i = first_body_level(text, text.lower().find('<head'))
    if i < 0:
        return text
    return text[:i] + LINK + '\n' + text[i:]


def add_dark_class(text: str) -> str:
    m = re.search(r'<body([^>]*)>', text, re.I)
    if not m:
        # VISA_ASSISTANT has no <body> at all: open one where the body starts
        i = first_body_level(text, text.lower().find('<head'))
        if i < 0:
            return text
        return text[:i] + '<body class="tool-dark">' + text[i:]
    attrs = m.group(1)
    if 'tool-dark' in attrs:
        return text
    if 'class="' in attrs:
        new = attrs.replace('class="', 'class="tool-dark ', 1)
    else:
        new = attrs + ' class="tool-dark"'
    return text[:m.start()] + '<body' + new + '>' + text[m.end():]


def add_aria(text: str, page: str, labels: dict) -> tuple[str, int]:
    added = 0
    for cid, label in labels.items():
        if (page, cid) in SKIP:
            continue
        label = OVERRIDES.get((page, cid), label)
        if not label:
            continue
        pat = re.compile(r'(<(?:input|select|textarea)\b[^>]*\bid="%s"[^>]*?)(/?>)' % re.escape(cid))
        m = pat.search(text)
        if not m or 'aria-label' in m.group(0):
            continue
        text = text[:m.start()] + m.group(1) + ' aria-label="' + htmllib.escape(label, quote=True) + '"' + m.group(2) + text[m.end():]
        added += 1
    return text, added


def fix_hub(text: str) -> str:
    # 1. drop the phantom NLW card (links to index.html, no such tool on the site)
    text = re.sub(r'\s*<a href="index\.html" class="tool-card">.*?</a>\n',
                  '\n', text, count=1, flags=re.S)
    # 2. add the orphaned auditor to the marketing section
    if 'AI_AUDITOR.html' not in text:
        i = text.find('VISA, MENU & MARKETING')
        if i < 0:
            i = text.find('VISA, MENU &amp; MARKETING')
        grid = text.find('<div class="tool-grid">', i)
        if grid > 0:
            end = text.find('\n', grid) + 1
            text = text[:end] + CARD + text[end:]
    return text


def main(apply_changes: bool) -> None:
    labels = json.loads(Path('/tmp/labels2.json').read_text())
    aria_total = 0
    for page in sorted(TOOLS.glob('*.html')):
        text = page.read_text(errors='ignore')
        original = text
        text = add_link(text)
        if page.name in DARK:
            text = add_dark_class(text)
        text, n = add_aria(text, page.name, {i['id']: i['label'] for i in labels.get(page.name, []) if i['id']})
        aria_total += n
        if text != original and apply_changes:
            page.write_text(text)
    hub = ROOT / 'tools.html'
    htext = hub.read_text()
    new_hub = fix_hub(htext)
    if new_hub != htext and apply_changes:
        hub.write_text(new_hub)
    print(f'{"applied" if apply_changes else "would apply"}: {aria_total} aria-labels; '
          f'hub {"changed" if new_hub != htext else "unchanged"}')
    if not apply_changes:
        print('dry run — pass --apply')


if __name__ == '__main__':
    main('--apply' in sys.argv)
