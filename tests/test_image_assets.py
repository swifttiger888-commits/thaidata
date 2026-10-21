#!/usr/bin/env python3
"""Images are served as WebP and every local reference resolves.

The recipe/menu JPEGs were 55.4 MB across 294 files (median 193 KB) and displayed
at 820 px. The .webp copies are 20.2 MB. Originals stay on disk as the fallback,
so this test only cares that nothing points at a file that is not there.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HTML = [p for p in REPO.rglob('*.html') if '.git' not in p.parts]
REF = re.compile(r'(?:src|href)="([^"]+\.(?:webp|jpe?g))"')


def resolve(page: Path, ref: str) -> Path | None:
    if re.match(r'^https?://', ref):
        if not re.match(r'^https?://(www\.)?thaidata\.uk/', ref):
            return None                  # someone else's image: not ours to check
    local = re.sub(r'^https?://[^/]+', '', ref)
    return REPO / local.lstrip('/') if local.startswith('/') else page.parent / local


def test_every_local_image_reference_resolves():
    missing = []
    for page in HTML:
        text = page.read_text(errors='ignore')
        for ref in REF.findall(text):
            target = resolve(page, ref)
            if target is not None and not target.exists():
                missing.append((str(page.relative_to(REPO)), ref))
    assert not missing, missing[:10]


def test_recipe_images_are_webp():
    jpgs = [p for p in REPO.rglob('*.jpg') if '.git' not in p.parts]
    webps = [p for p in REPO.rglob('*.webp') if '.git' not in p.parts]
    assert len(webps) >= 290, len(webps)
    assert webps, 'no webp copies'
    # every jpeg that sits beside a webp must have one
    without = [j.name for j in jpgs if not j.with_suffix('.webp').exists()]
    assert not without, without[:10]


def test_webp_is_smaller_overall():
    jpg_bytes = sum(p.stat().st_size for p in REPO.rglob('*.jpg') if '.git' not in p.parts)
    webp_bytes = sum(p.stat().st_size for p in REPO.rglob('*.webp') if '.git' not in p.parts)
    assert webp_bytes < jpg_bytes * 0.6, (webp_bytes, jpg_bytes)
