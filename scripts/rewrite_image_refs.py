#!/usr/bin/env python3
"""Point HTML at the .webp copies where they exist.

Only rewrites a .jpg reference when the matching .webp is on disk, so an external
image or an unconverted one is left alone. Originals stay, so a miss degrades to
the old file rather than a 404.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# capture the path ending in .jpg, including absolute-URL paths
REF = re.compile(r'((?:https?://[^"\'\s]+?)?(?:/|(?<=["\'])|(?<=\())?[\w\-./]*?[\w\-]+)\.jpg')


def main(apply_changes: bool) -> None:
    pages = [p for p in ROOT.rglob('*.html') if '.git' not in p.parts]
    changed = 0
    refs = 0
    for page in pages:
        text = page.read_text(errors='ignore')
        if '.jpg' not in text:
            continue

        def sub(m: re.Match) -> str:
            nonlocal refs
            path = m.group(1)
            # strip a scheme+host so we can test the file locally
            local = re.sub(r'^https?://[^/]+', '', path)
            if local.startswith('/'):
                probe = ROOT / local.lstrip('/')
            else:
                probe = (page.parent / local)
            if probe.with_suffix('.webp').exists():
                refs += 1
                return path + '.webp'
            return m.group(0)

        new = REF.sub(sub, text)
        if new != text:
            changed += 1
            if apply_changes:
                page.write_text(new)
    print(f'{"rewrote" if apply_changes else "would rewrite"} {changed} pages, {refs} refs')
    if not apply_changes:
        print('dry run — pass --apply')


if __name__ == '__main__':
    main('--apply' in sys.argv)
