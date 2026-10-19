#!/usr/bin/env python3
"""Prune menu pages that shouldn't be public.

A menu page is only worth indexing if it is a menu. Two failure shapes slipped
through the batch (they pass "some dishes" but fail as content):

  * thin      — fewer than MIN_ITEMS dishes: almost always a partial capture
                (one column, one tab, a specials board) rather than the menu
  * unpriced  — fewer than MIN_PRICED of dishes carry a price: usually an
                allergen chart or wine list, not a menu with prices

Deletes the JSON and its rendered page, so the listing loses its "Full menu"
link on the next generator run. Idempotent; --dry-run lists only.
"""
import argparse
import glob
import json
import os
import re
import shutil

REPO = '/opt/thaidata-repo'
MIN_ITEMS = 10
MIN_PRICED = 0.5


def slug(s):
    return re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', (s or '').lower())).strip('-')


def page_dir(d):
    city = slug(d['city'])
    for form in (slug(d['restaurant']), slug(d['restaurant'].replace("'", ''))):
        p = os.path.join(REPO, 'r', city, form, 'menu')
        if os.path.isdir(p):
            return p
    fsa = str(d.get('fsa_id') or '')
    cdir = os.path.join(REPO, 'r', city)
    if fsa and os.path.isdir(cdir):
        for name in sorted(os.listdir(cdir)):
            idx = os.path.join(cdir, name, 'index.html')
            if os.path.isfile(idx) and f'"{fsa}"' in open(idx, encoding='utf-8', errors='ignore').read(6000):
                return os.path.join(cdir, name, 'menu')
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    pruned = []
    for f in sorted(glob.glob(os.path.join(REPO, 'data/menus/*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        items = [i for arr in (d.get('categories') or {}).values() if isinstance(arr, list)
                 for i in arr if isinstance(i, dict)]
        priced = sum(1 for i in items if i.get('price'))
        reason = None
        if len(items) < MIN_ITEMS:
            reason = f'thin: {len(items)} items'
        elif items and priced / len(items) < MIN_PRICED:
            reason = f'unpriced: {priced}/{len(items)}'
        if not reason:
            continue
        pd = page_dir(d)
        pruned.append((os.path.basename(f), d['restaurant'], d['city'], reason, pd))
        if not args.dry_run:
            os.remove(f)
            if pd:
                shutil.rmtree(pd, ignore_errors=True)
    for name, rest, city, reason, pd in pruned:
        print(f'  {"would prune" if args.dry_run else "pruned"}: {rest} ({city}) — {reason}')
    print(f'{"would prune" if args.dry_run else "pruned"} {len(pruned)} menus')


if __name__ == '__main__':
    main()
