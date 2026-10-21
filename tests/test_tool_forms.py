#!/usr/bin/env python3
"""Form affordances on the 21 tool pages.

Measured before this guard existed: three tools had typed text at 1.0-1.6:1
against their own field background (white-on-white on one of them), two more had
no visible field boundary, and nine sliders had no visible rail. The shared
stylesheet fixes that; this test stops a page drifting back.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOOLS = REPO / 'tools'
PAGES = sorted(TOOLS.glob('*.html'))
DARK = {'AI_AUDITOR.html', 'WHOLESALE_BENCHMARKER.html',
        'PROFIT_MARGIN_DEFENDER.html', 'VISA_ASSISTANT.html'}


def test_every_tool_loads_the_shared_form_stylesheet():
    missing = [p.name for p in PAGES if 'href="/css/tool-forms.css"' not in p.read_text(errors='ignore')]
    assert not missing, missing


def test_dark_panel_tools_are_marked():
    unmarked = [p.name for p in PAGES
                if p.name in DARK and 'tool-dark' not in p.read_text(errors='ignore')]
    assert not unmarked, unmarked


def test_stylesheet_carries_the_fixes():
    css = (REPO / 'css' / 'tool-forms.css').read_text()
    assert 'input[type="range"]::-webkit-slider-thumb' in css, 'slider thumb rule missing'
    assert 'body.tool-dark' in css, 'dark-panel variant missing'
    assert 'min-height: 40px' in css, 'touch-target rule missing'
    # the field border must be a solid colour, not a near-invisible white alpha
    assert 'border: 1px solid #9A928D !important' in css


def test_inputs_that_were_unlabelled_now_have_a_name():
    without = []
    for page in PAGES:
        text = page.read_text(errors='ignore')
        for m in re.finditer(r'<(input|select|textarea)\b[^>]*>', text):
            tag = m.group(0)
            if any(x in tag for x in ('type="hidden"', 'type="submit"', 'type="button"')):
                continue
            cid = re.search(r'id="([^"]+)"', tag)
            if not cid:
                continue
            if 'aria-label' in tag:
                continue
            # a real <label for=...> nearby also counts
            if re.search(r'<label[^>]*for="%s"' % re.escape(cid.group(1)), text):
                continue
            without.append((page.name, cid.group(1)))
    assert not without, without[:10]


def test_hub_has_no_card_pointing_at_the_homepage():
    hub = (REPO / 'tools.html').read_text()
    assert 'href="index.html" class="tool-card"' not in hub
    assert 'tools/AI_AUDITOR.html' in hub, 'AI auditor still orphaned'
