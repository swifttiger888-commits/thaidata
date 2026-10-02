#!/usr/bin/env python3
"""Match menu dish names against the recipe library via data/recipe_aliases.json.

Rules:
- Thai-script substring -> strong hit (score 9)
- alias of 2+ tokens: every token must appear in the menu item (bag of words)
- alias of 1 token: token must appear in the menu item
- longest alias wins; one match per item.

Usage:
  match_menu_recipes.py --check [menu.json ...]   # dry run, print hits+misses
  match_menu_recipes.py --page menu.json out.html # build one menu page with links
"""
import json, re, sys, os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILLER = {"the", "a", "an", "with", "without", "and", "or", "of", "style", "fresh"}


def tokens(s):
    s = s.lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^\w\s]", " ", s)
    return [t for t in s.split() if t not in FILLER]


class Matcher:
    def __init__(self, alias_path):
        self.map = json.load(open(alias_path, encoding="utf-8"))
        self.alias_tok = {
            s: [tokens(a) for a in e.get("aliases", []) if tokens(a)]
            for s, e in self.map.items()
        }

    def match(self, name):
        t = tokens(name)
        tset = set(t)
        for slug, e in self.map.items():
            for th in e.get("thai", []):
                if th and th in name:
                    return slug
        best = None
        for slug, als in self.alias_tok.items():
            for a in als:
                # >=4-token aliases are specific enough for bag-of-words;
                # 2-3 token aliases must match as an adjacent phrase;
                # 1-token aliases need exact token presence.
                if len(a) >= 4:
                    hit = all(x in tset for x in a)
                elif len(a) > 1:
                    hit = " ".join(a) in " ".join(t)
                else:
                    hit = a[0] in tset
                if hit and (best is None or len(a) > best[1]):
                    best = (slug, len(a))
        return best[0] if best else None


def load_menus(paths):
    out = []
    for p in paths:
        d = json.load(open(p, encoding="utf-8"))
        out.append((p, d))
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    mode = args[0] if args and args[0].startswith("--") else "--check"
    rest = args[1:] if mode.startswith("--") else args
    m = Matcher(os.path.join(REPO, "data/recipe_aliases.json"))
    if not rest:
        import glob
        rest = glob.glob(os.path.join(REPO, "data/menus/*.json"))
    total = hit = 0
    hits = {}
    for p in rest:
        d = json.load(open(p, encoding="utf-8"))
        for cat, items in (d.get("categories") or {}).items():
            for it in items:
                nm = (it.get("name") or "").strip()
                if not nm:
                    continue
                total += 1
                h = m.match(nm)
                if h:
                    hit += 1
                    hits.setdefault(h, 0)
                    hits[h] += 1
    print(f"HITS {hit}/{total} ({100*hit/max(total,1):.0f}%) across {len(set(hits))} recipes")
    for s, n in sorted(hits.items(), key=lambda x: -x[1]):
        print(f"  {s:28s} {n}")
