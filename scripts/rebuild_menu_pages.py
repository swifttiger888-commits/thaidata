#!/usr/bin/env python3
"""Rebuild every menu page from its JSON.

The page is a pure function of data/menus/*.json, but the batch writes JSON and
page in one pass; a later JSON repair leaves the page stale (that is how CI's
render guard caught 23 menus with double-escaped names). This is the reconcile
step: JSON is the source, pages are always rebuilt from it.

Usage: python3 scripts/rebuild_menu_pages.py [--check]
"""
import glob
import json
import os
import re
import subprocess
import sys

REPO = '/opt/thaidata-repo'


def slug(s):
    return re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', (s or '').lower())).strip('-')


def page_path(d):
    city = slug(d['city'])
    for form in (slug(d['restaurant']), slug(d['restaurant'].replace("'", ''))):
        p = os.path.join(REPO, 'r', city, form, 'menu', 'index.html')
        if os.path.isfile(p):
            return p
    # Names in the menu JSON often carry a suffix the listing slug drops
    # ("Thai Cottage (Tadworth)" -> r/dacorum/thai-cottage). Match on the
    # venue's FSA id against the listing pages in this city instead.
    fsa = str(d.get('fsa_id') or '')
    cdir = os.path.join(REPO, 'r', city)
    if fsa and os.path.isdir(cdir):
        for name in sorted(os.listdir(cdir)):
            idx = os.path.join(cdir, name, 'index.html')
            if os.path.isfile(idx) and f'"{fsa}"' in open(idx, encoding='utf-8', errors='ignore').read(6000):
                return os.path.join(cdir, name, 'menu', 'index.html')
    return None


def main():
    check = '--check' in sys.argv
    jsons = sorted(glob.glob(os.path.join(REPO, 'data/menus/*.json')))
    built = missing = 0
    for j in jsons:
        d = json.load(open(j, encoding='utf-8'))
        p = page_path(d)
        if not p:
            missing += 1
            print(f'  no page: {os.path.basename(j)}')
            continue
        rel = os.path.relpath(p, REPO)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if check:
            continue
        r = subprocess.run([os.path.join(REPO, '.venv/bin/python'), 'scripts/build_menu_page.py', j, rel],
                           cwd=REPO, capture_output=True, text=True)
        if r.returncode == 0:
            built += 1
        else:
            print(f'  build failed {os.path.basename(j)}: {(r.stderr or "").strip()[-120:]}')
    print(f'{"checked" if check else "rebuilt"} {built} pages, {missing} JSONs with no page')


if __name__ == '__main__':
    main()
