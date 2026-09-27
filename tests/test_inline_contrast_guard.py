#!/usr/bin/env python3
"""Guard: no inline white text without a background of its own.

On the ivory theme an inline ``color:white`` / ``color:#fff`` that does NOT
paint a background in the same style attribute renders at contrast ratio 1.0 —
invisible text.

Regression this guards (Sep 2026): the FSA auto-refresh re-ran
``generate_city_pages.py``, whose ``build_faq_html()`` emitted ``color:white``
for the FAQ ``<summary>`` rows sitting on ``#FFFFFF`` cards — 928 questions
unreadable across 251 city pages. The Sep 20 contrast sweep had fixed the HTML
output but not the generators, so the next pipeline run silently re-broke it.

House rule (from that sweep): white text is only allowed when the same style
attribute also paints a background (e.g. a grey chip with white text).
Everything else must use a theme colour such as ``var(--ink)``.

Run: python -m pytest tests/test_inline_contrast_guard.py -v
"""
import glob
import os
import re

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))

PAT = re.compile(r'style="[^"]*color:\s*(?:white|#fff(?:fff)?)[^"]*"', re.I)
BG = re.compile(r'background', re.I)


def _scan(paths):
    offenders = []
    for path in sorted(paths):
        with open(path, encoding='utf-8', errors='ignore') as fh:
            text = fh.read()
        for m in PAT.finditer(text):
            if not BG.search(m.group(0)):
                line = text[:m.start()].count('\n') + 1
                offenders.append(f'{os.path.relpath(path, REPO)}:{line} {m.group(0)[:100]}')
    return offenders


def test_generators_emit_no_unbacked_white_text():
    files = glob.glob(os.path.join(REPO, 'scripts', '*.py'))
    assert len(files) > 20, 'scripts/ scan looks wrong — check REPO path'
    offenders = _scan(files)
    assert not offenders, (
        f'{len(offenders)} inline white style(s) with no background in scripts/*.py — '
        'these will render invisible on the ivory theme:\n' + '\n'.join(offenders[:10]))


def test_city_and_chain_pages_have_no_unbacked_white_text():
    files = (glob.glob(os.path.join(REPO, 'cities', '*.html'))
             + glob.glob(os.path.join(REPO, 'chains', '*.html')))
    assert len(files) > 100, 'cities/ scan looks wrong — check REPO path'
    offenders = _scan(files)
    assert not offenders, (
        f'{len(offenders)} page(s) contain inline white text with no background:\n'
        + '\n'.join(offenders[:10]))
