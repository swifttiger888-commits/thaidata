#!/usr/bin/env python3
"""Fonts are served from our own origin.

Google Fonts was a render-blocking third-party request on 2,064 pages, and 1,173 of
them also pulled Instrument Serif that the design no longer uses. Nothing may
reintroduce a hotlinked font.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FONTS_CSS = REPO / 'css' / 'fonts.css'
HTML = [p for p in REPO.rglob('*.html') if '.git' not in p.parts]


def test_no_page_hotlinks_google_fonts():
    offenders = [str(p.relative_to(REPO)) for p in HTML
                 if 'fonts.googleapis.com' in p.read_text(errors='ignore')
                 or 'fonts.gstatic.com' in p.read_text(errors='ignore')]
    assert not offenders, offenders[:10]


def test_pages_that_use_the_typefaces_load_our_stylesheet():
    # brand-image.html is a design mock and tools/VISA_ASSISTANT.html is a
    # self-contained tool with its own stack; neither is a ThaiData page.
    exempt = {'brand-image.html', 'tools/VISA_ASSISTANT.html'}
    missing = []
    for page in HTML:
        rel = str(page.relative_to(REPO))
        text = page.read_text(errors='ignore')
        if rel in exempt or ('Archivo' not in text and 'Inter' not in text):
            continue
        if 'href="/css/fonts.css"' not in text:
            missing.append(rel)
    assert not missing, missing[:10]
    assert len(HTML) - len(missing) > 2000


def test_font_stylesheet_is_complete_and_files_exist():
    css = FONTS_CSS.read_text()
    faces = re.findall(r'@font-face\s*{([^}]*)}', css)
    assert len(faces) == 8, len(faces)
    families = {m.group(1) for f in faces if (m := re.search(r"font-family:\s*'([^']+)'", f))}
    assert families == {'Archivo', 'Inter', 'Instrument Serif'}, families
    for src in re.findall(r'url\((/assets/fonts/[^)]+)\)', css):
        assert (REPO / src.lstrip('/')).exists(), src
    # variable ranges, not fixed weights: a fixed face would fake the missing ones
    assert 'font-weight: 500 800' in css
    assert 'font-weight: 100 900' in css
