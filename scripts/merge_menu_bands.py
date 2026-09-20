#!/usr/bin/env python3
"""
ThaiData UK — merge per-band menu extractions into one verified menu.

WHY THIS EXISTS
---------------
Extracting a multi-column menu by slicing it into strips produces DUPLICATE dish
numbers: two strips that overlap can both report dish 80, sometimes with different
names (one correct, one a misread of a neighbouring number).

An earlier ad-hoc merge keyed on dish number and broke ties by "longer name wins".
That silently produced a wrong dish: the correct "80. Khao Pad Puu (Crab Fried Rice)"
(31 chars) lost to a misread "80. Ga-Prao Neua / Moo Daeng with Rice" (34 chars).

So this module NEVER silently resolves a conflict. It:
  * keeps the entry that carries a price over one that does not,
  * reports every remaining conflict for human/vision review,
  * exits non-zero in --strict mode when unresolved conflicts exist.

Usage:
    python3 scripts/merge_menu_bands.py bands/*.raw.txt > merged.json
    python3 scripts/merge_menu_bands.py --strict --report conflicts.txt bands/*.raw.txt
"""
from __future__ import annotations

import argparse
import json
import re
import sys

NUM_RE = re.compile(r"^(\d+)\.\s*(.*)$")


def load(path: str) -> dict:
    """Parse one band response, tolerating markdown fences."""
    text = open(path, encoding="utf-8").read().strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    return json.loads(text)


def normalise(name: str) -> tuple[int | None, str]:
    name = re.sub(r"\s+", " ", name or "").strip()
    name = re.sub(r"\s*\bC\s?\d\b\s*", " ", name)      # chilli-level marker
    name = re.sub(r"\s*\bV\b\s*$", "", name).strip()    # vegetarian marker
    m = NUM_RE.match(name)
    if m:
        return int(m.group(1)), m.group(2).strip()
    return None, name


def merge(paths: list[str]) -> tuple[dict, list[dict]]:
    """Merge band files into {key: item}. Returns (items, conflicts).

    A conflict is a dish number seen more than once with materially different names,
    after preferring the price-bearing entry.
    """
    seen: dict[str, list[dict]] = {}

    for path in paths:
        band = load(path)
        for cat in band.get("categories", []):
            cat_name = re.sub(r"\s+", " ", (cat.get("name") or "")).strip()
            for it in cat.get("items", []):
                num, name = normalise(it.get("name", ""))
                if not name:
                    continue
                key = f"n{num}" if num is not None else "nm:" + name.lower()
                seen.setdefault(key, []).append({
                    "num": num,
                    "name": name,
                    "description": (it.get("description") or "").strip(),
                    "price": it.get("price"),
                    "category": cat_name,
                    "source": path,
                })

    items: dict[str, dict] = {}
    conflicts: list[dict] = []

    for key, cands in seen.items():
        if len(cands) == 1:
            items[key] = cands[0]
            continue

        # Prefer entries that carry a price — a price-bearing entry is a complete
        # printed line; a price-less duplicate is usually a misread number.
        priced = [c for c in cands if c["price"]]
        pool = priced or cands

        # Among equally-complete candidates, pick the one whose name is a PREFIX of
        # or equal to another candidate's — printed names are the shorter, cleaner
        # form. Never "longest wins": that is what produced the original error.
        names = {c["name"] for c in pool}
        distinct = {n for n in names if not any(n != o and o.startswith(n) for o in names)}

        winner = pool[0]
        if len(distinct) > 1:
            conflicts.append({
                "key": key,
                "number": cands[0]["num"],
                "candidates": [{"name": c["name"], "price": c["price"],
                                "category": c["category"], "source": c["source"]}
                               for c in cands],
                "auto_chosen": winner["name"],
                "reason": "same dish number, materially different names — needs review",
            })
        else:
            # Same dish, different depth of transcription: take the fullest copy.
            winner = max(pool, key=lambda c: (bool(c["price"]), len(c["description"])))

        merged = dict(winner)
        for c in cands:
            if c["price"] and not merged["price"]:
                merged["price"] = c["price"]
            if len(c["description"]) > len(merged["description"]):
                merged["description"] = c["description"]
            if c["category"] and not merged["category"]:
                merged["category"] = c["category"]
        items[key] = merged

    return items, conflicts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--report", help="write the conflict report to this path")
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero if any conflict needs review")
    args = ap.parse_args()

    items, conflicts = merge(args.paths)

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(conflicts, f, indent=2, ensure_ascii=False)

    out = {
        "items": {k: v for k, v in sorted(items.items())},
        "conflicts": conflicts,
    }
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)

    print(f"\nmerged {len(items)} items, {len(conflicts)} conflicts need review",
          file=sys.stderr)
    for c in conflicts:
        names = " | ".join(f'{x["name"]} ({x["price"] or "no price"})' for x in c["candidates"])
        print(f"  dish {c['number']}: {names}", file=sys.stderr)

    return 1 if (args.strict and conflicts) else 0


if __name__ == "__main__":
    raise SystemExit(main())
