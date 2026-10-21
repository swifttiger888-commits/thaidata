#!/usr/bin/env python3
"""Convert recipe/menu JPEGs to WebP, keeping the originals.

294 JPEGs, 55.4 MB, median 193 KB, all 1408x768 or similar and displayed at
820 px wide. Re-encoding at 1100 px (covers 1.34x for retina) and q78 keeps the
same layout dimensions while cutting the bytes roughly in half.

Originals stay on disk: nothing 404s if an old reference survives, and the
conversion can be re-run or reverted without re-downloading anything.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
MAX_W = 1100
QUALITY = 78


def convert(jpg: Path) -> tuple[int, int]:
    im = Image.open(jpg)
    if im.mode != 'RGB':
        im = im.convert('RGB')
    w, h = im.size
    if w > MAX_W:
        im = im.resize((MAX_W, round(h * MAX_W / w)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, 'WEBP', quality=QUALITY, method=6)
    out = jpg.with_suffix('.webp')
    out.write_bytes(buf.getvalue())
    return jpg.stat().st_size, len(buf.getvalue())


def main() -> None:
    jpgs = sorted(p for p in ROOT.rglob('*.jpg') if '.git' not in p.parts)
    before = after = 0
    for i, jpg in enumerate(jpgs, 1):
        try:
            b, a = convert(jpg)
        except Exception as exc:              # report the real error, keep going
            print('FAIL', jpg.relative_to(ROOT), exc)
            continue
        before += b
        after += a
        if i % 50 == 0:
            print(f'{i}/{len(jpgs)}  {before / 1e6:.1f} MB -> {after / 1e6:.1f} MB', flush=True)
    print(f'{len(jpgs)} files  {before / 1e6:.1f} MB -> {after / 1e6:.1f} MB  '
          f'({100 * (1 - after / before):.0f}% smaller)')


if __name__ == '__main__':
    main()
