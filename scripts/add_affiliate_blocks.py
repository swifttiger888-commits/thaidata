#!/usr/bin/env python3
"""Insert/refresh the Thai-grocery affiliate block on consumer content pages.

Idempotent and data-driven (data/affiliates.json):
  - groceries.enabled=true  → block inserted before the first <footer>,
                              once, wrapped in marker comments.
  - groceries.enabled=false → any existing marked block is removed.

Usage:
    python scripts/add_affiliate_blocks.py            # Apply
    python scripts/add_affiliate_blocks.py --check    # Report only
"""
from __future__ import annotations

import argparse
import json
import sys
from html import escape as html_escape
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO / "data" / "affiliates.json"
START = "<!-- AFFILIATE:groceries -->"
END = "<!-- END:AFFILIATE:groceries -->"


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH) as f:
        return json.load(f)


def build_grocery_block(cfg: dict[str, Any]) -> str:
    groc = cfg.get("groceries", {})
    if not groc.get("enabled"):
        return ""
    items = []
    for merchant in groc.get("merchants", []):
        name = html_escape(merchant["name"])
        url = html_escape(merchant["url"], quote=True)
        note = html_escape(merchant.get("note", ""))
        key = merchant["name"].lower().replace(" ", "-")
        line = (
            f'<a href="{url}" rel="sponsored nofollow" data-affiliate="{key}">'
            f"{name}</a>"
        )
        if note:
            line += f" &mdash; {note}"
        items.append(f"        <li>{line}</li>")
    disclosure = html_escape(groc.get("disclosure", ""))
    parts = [
        '    <div class="section affiliate">',
        '      <div class="wrap">',
        "        <h2><em>Cook</em> Thai at home</h2>",
        "        <p>Stock up on Thai ingredients and groceries:</p>",
        "        <ul>",
        *items,
        "        </ul>",
    ]
    if disclosure:
        parts.append(f'        <p class="affiliate-note">{disclosure}</p>')
    parts.extend(["      </div>", "    </div>"])
    return "\n".join(parts)


def update_page(path: Path, block: str) -> str:
    """Apply the block to one page. Returns 'ok' | 'skipped' | 'missing' | 'no-footer'."""
    if not path.exists():
        return "missing"
    source = path.read_text(encoding="utf-8")
    changed = False

    if START in source and END in source:
        left = source.index(START) + len(START)
        right = source.index(END, left)
        new_source = (
            source[:left] + ("\n" + block + "\n" if block else "") + source[right:]
        )
        if new_source != source:
            source, changed = new_source, True
    elif block:
        idx = source.lower().find("<footer")
        if idx == -1:
            return "no-footer"
        source = (
            source[:idx]
            + START
            + "\n"
            + block
            + "\n"
            + END
            + "\n"
            + source[idx:]
        )
        changed = True

    if changed:
        path.write_text(source, encoding="utf-8")
        return "ok"
    return "skipped"


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage grocery affiliate blocks")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report what would change without writing",
    )
    args = parser.parse_args()

    cfg = load_config()
    pages = cfg.get("grocery_pages", [])
    block = build_grocery_block(cfg)
    state = "ENABLED" if block else "disabled (no blocks rendered)"

    print(f"Affiliate groceries: {state}")
    print(f"Pages in config: {len(pages)}")
    ok = skipped = 0
    for rel in pages:
        path = REPO / rel
        if args.check:
            if not path.exists():
                print(f"  ⚠️  missing: {rel}")
                continue
            source = path.read_text(encoding="utf-8")
            has_block = START in source and END in source
            wants_block = bool(block) and not has_block
            wants_remove = (not block) and has_block
            if wants_block or wants_remove:
                print(f"  🔷 would change: {rel}")
            else:
                skipped += 1
            continue
        result = update_page(path, block)
        if result == "ok":
            print(f"  ✅ {rel}")
            ok += 1
        elif result == "missing":
            print(f"  ❌ missing on disk: {rel}")
        elif result == "no-footer":
            print(f"  ⚠️  no <footer> found: {rel}")
        else:
            skipped += 1
    print(f"Done: {ok} written, {skipped} unchanged")
    sys.exit(0)


if __name__ == "__main__":
    main()
