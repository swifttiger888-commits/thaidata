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


# ── Broader sweeps (Oct 2026) ────────────────────────────────────────────────
# The checks above only cover inline styles in scripts/, cities/ and chains/.
# Three contrast bugs escaped through the gaps: pale text in .highlight-box CSS
# rules on root pages, white nav links on a white nav bar, and stale muted-grey
# tokens (#9C918C at 2.87:1). These tests close those gaps.

def _lum(hex_colour):
    h = hex_colour.lstrip('#')
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (f(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _all_sources():
    for pattern in ('*.html', 'scripts/*.py'):
        yield from glob.glob(os.path.join(REPO, pattern))
    yield from glob.glob(os.path.join(REPO, 'cities', '*.html'))
    yield from glob.glob(os.path.join(REPO, 'chains', '*.html'))


def test_muted_ink_tokens_meet_aa_contrast():
    """--ink3/--ink4 are the secondary text tokens; they must clear 4.5:1 on the
    two backgrounds they are actually painted on (#FFFFFF cards, #FBF7F0 page)."""
    bad = []
    for path in sorted(_all_sources()):
        with open(path, encoding='utf-8', errors='ignore') as fh:
            text = fh.read()
        for m in re.finditer(r'--ink[34]:\s*(#[0-9A-Fa-f]{6})', text):
            colour = m.group(1)
            worst = min(_contrast(colour, '#FFFFFF'), _contrast(colour, '#FBF7F0'))
            if worst < 4.5:
                bad.append(f'{os.path.relpath(path, REPO)} {m.group(0)} -> {worst:.2f}:1')
    assert not bad, (
        'muted ink tokens below WCAG AA (4.5:1):\n' + '\n'.join(sorted(set(bad))[:10]))


def test_no_light_text_inside_pale_highlight_boxes():
    """A .highlight-box is always a pale tint or white. Any near-white text
    declared for it renders at ~1.1:1 — invisible."""
    pat = re.compile(r'\.highlight-box[^{}]*\{([^}]*)\}')
    light = re.compile(r'color:\s*(?:white|#fff(?:fff)?|rgba\(\s*255\s*,\s*255\s*,\s*255)', re.I)
    bad = []
    for path in sorted(_all_sources()):
        with open(path, encoding='utf-8', errors='ignore') as fh:
            text = fh.read()
        for m in pat.finditer(text):
            if light.search(m.group(1)):
                bad.append(f'{os.path.relpath(path, REPO)}: {m.group(0)[:90]}')
    assert not bad, 'near-white text inside a pale .highlight-box:\n' + '\n'.join(sorted(set(bad))[:10])


def test_light_nav_bars_carry_no_white_text():
    """nav paints background: var(--dark). When --dark resolves light (it does on
    every page except one), white text inside <nav> is unreadable."""
    bad = []
    for path in sorted(glob.glob(os.path.join(REPO, '*.html')) + glob.glob(os.path.join(REPO, '**', '*.html'), recursive=True)):
        with open(path, encoding='utf-8', errors='ignore') as fh:
            text = fh.read()
        dark = re.search(r'--dark:\s*(#[0-9A-Fa-f]{6})', text)
        if not dark or _lum(dark.group(1)) < 0.5:
            continue
        for nav in re.findall(r'<nav[\s\S]*?</nav>', text):
            if re.search(r'color:\s*(?:rgba\(\s*255\s*,\s*255\s*,\s*255|white|#fff)', nav, re.I):
                bad.append(os.path.relpath(path, REPO))
    assert not bad, 'white text inside a light nav bar:\n' + '\n'.join(sorted(set(bad))[:10])
