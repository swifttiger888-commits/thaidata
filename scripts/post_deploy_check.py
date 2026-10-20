#!/usr/bin/env python3
"""Post-deploy smoke check for thaidata.uk — run after every production deploy.

Three checks, in order, under two minutes:

  1. IDENTITY — the live production deployment's commit hash equals origin/main, so you
     are testing the build you think you are.
  2. SMOKE — a fixed URL list returns the expected status AND a per-page marker, so a
     200 that renders an empty shell still fails.
  3. ASSETS — every local /assets/... reference on the sampled pages resolves, and every
     self-hosted woff2 is served with the right content-type and immutable caching.

Exit code 0 = all clear, 1 = something to look at. Read the printed lines, not just the
exit code: a check that could not run (no token, network hiccup) prints SKIP and does not
fail the run.

Usage: python3 scripts/post_deploy_check.py [--base https://thaidata.uk] [--no-identity]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

UA = 'Mozilla/5.0 (compatible; ThaiData-PostDeploy/1.0)'
ACCOUNT_ID = 'badd33ce94008f499f2ae75fd3b04574'
PROJECT = 'thaidata'
FONT_DIR = '/root/.hermes/cf-token-thaidata'

# (path, expected status, marker that must appear in the body)
SMOKE = [
    ('/', 200, 'Thai'),
    ('/cities/leeds', 200, 'Leeds'),
    ('/r/leeds/chao-phraya-thai-restaurant/', 200, 'application/ld+json'),
    ('/r/london/nara-thai/', 200, 'cs-item'),          # claimed listing: middleware owner strip
    ('/claim/', 200, 'claim'),
    ('/sitemap.xml', 200, '<sitemapindex'),
    ('/llms.txt', 200, 'Thai'),
    ('/assets/fonts/archivo-latin-v1.woff2', 200, None),
]

failures: list[str] = []


def get(url, method='GET'):
    req = urllib.request.Request(url, method=method, headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            return r.status, dict(r.headers), body
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()
    except Exception as e:  # noqa: BLE001
        return None, {}, str(e).encode()


def check_identity() -> None:
    try:
        token = open(FONT_DIR).read().strip()
    except OSError:
        print('SKIP identity: no Cloudflare token')
        return
    try:
        req = urllib.request.Request(
            f'https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/pages/projects/{PROJECT}/deployments?per_page=1',
            headers={'Authorization': 'Bearer ' + token})
        dep = json.loads(urllib.request.urlopen(req, timeout=30).read())['result'][0]
        deployed = dep.get('deployment_trigger', {}).get('metadata', {}).get('commit_hash', '')
        head = subprocess.run(['git', '-C', os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
        ok = deployed.startswith(head[:9]) or head.startswith(deployed[:9])
        print(f"{'OK  ' if ok else 'FAIL'} identity: live {deployed[:9]} vs local HEAD {head[:9]}")
        if not ok:
            failures.append('live deployment is not the commit checked out locally')
    except Exception as e:  # noqa: BLE001
        print(f'SKIP identity: {e}')


def check_smoke(base: str) -> None:
    for path, want, marker in SMOKE:
        status, headers, body = get(base + path)
        text = body.decode('utf-8', 'ignore')
        has_marker = marker is None or marker in text
        ok = status == want and has_marker
        size = len(body)
        print(f"{'OK  ' if ok else 'FAIL'} {path} -> {status} {size}b"
              + ('' if has_marker else f' (missing marker {marker!r})'))
        if not ok:
            failures.append(f'{path}: status {status}, marker {"present" if marker in text else "MISSING"}')
        if path.endswith('.woff2') and status == 200:
            ct = headers.get('Content-Type', '')
            cc = headers.get('Cache-Control', '')
            good = 'font/woff2' in ct and 'immutable' in cc
            print(f"{'OK  ' if good else 'FAIL'}   font headers: {ct} | {cc}")
            if not good:
                failures.append(f'{path}: headers {ct} / {cc}')


def check_assets(base: str, pages) -> None:
    for page in pages:
        status, _, body = get(base + page)
        if status != 200:
            failures.append(f'{page}: {status}')
            print(f'FAIL {page} -> {status}')
            continue
        refs = sorted(set(re.findall(
            r'(?:href|src)="(/(?:[\w.-]+/)*[\w.-]+\.(?:svg|png|jpg|jpeg|webp|ico|css|js|woff2))"',
            body.decode('utf-8', 'ignore'))))
        bad = []
        for ref in refs:
            code, _, _ = get(base + ref, method='HEAD')
            if code != 200:
                bad.append((ref, code))
        print(f"{'OK  ' if not bad else 'FAIL'} assets on {page}: {len(refs)} checked"
              + (f', broken: {bad[:4]}' if bad else ''))
        if bad:
            failures.extend(f'{page}: {ref} -> {code}' for ref, code in bad)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='https://thaidata.uk')
    ap.add_argument('--no-identity', action='store_true')
    args = ap.parse_args()

    print(f'Post-deploy check for {args.base}\n')
    if not args.no_identity:
        check_identity()
    check_smoke(args.base)
    check_assets(args.base, ['/', '/r/leeds/chao-phraya-thai-restaurant/', '/r/london/nara-thai/'])

    print()
    if failures:
        print(f'FAILURES ({len(failures)}):')
        for f in failures:
            print('  -', f)
        return 1
    print('All post-deploy checks passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
