#!/usr/bin/env python3
"""Guards for the self-hosted webfont rollout (scripts/site_fonts.py).

The rollout is flag-gated (SELF_HOST_FONTS=1). Two things can silently break it:
  1. the flag is on but the woff2 assets are missing from /assets/fonts -> every page
     references 404s and falls back, with no error anywhere;
  2. the generator template changes shape and the swap stops matching, leaving pages
     on Google Fonts while the build reports success.

Run: python3 tests/test_self_hosted_fonts.py
"""
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'scripts'))

import site_fonts  # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)


def main():
    # 1. Assets present, non-empty, and served with a version suffix (immutable cache).
    for f in site_fonts.REQUIRED_ASSETS:
        p = os.path.join(site_fonts.FONT_DIR, f)
        check(os.path.isfile(p), f'missing font asset: {f}')
        if os.path.isfile(p):
            check(os.path.getsize(p) > 10_000, f'font asset suspiciously small: {f}')
            check(re.search(r'-v\d+\.woff2$', f) is not None,
                  f'font asset not version-suffixed (breaks immutable caching): {f}')

    # 2. Flag off is a no-op — the revert path must be exact.
    sample = '<head>\n  <link href="https://fonts.googleapis.com/css2?family=Inter&display=swap" rel="stylesheet">\n</head>'
    check(site_fonts.inject(sample, on=False) == sample, 'inject(on=False) altered the html')

    # 3. Flag on: Google origins gone, @font-face + preload present, fallback metrics kept.
    out = site_fonts.inject(sample, on=True)
    check('fonts.googleapis.com' not in out and 'fonts.gstatic.com' not in out,
          'Google Fonts origins survived the swap')
    check('@font-face' in out and 'font-display: swap' in out, 'no @font-face emitted')
    check('rel="preload"' in out and 'as="font"' in out and 'crossorigin' in out,
          'font preload missing or lacks crossorigin (double download)')
    check('unicode-range' in out, 'unicode-range lost — latin-ext would load on every page')
    check('/assets/fonts/' in out, 'font URLs are not root-absolute (break on /r/<city>/<slug>/)')

    # 4. A template with no Google Fonts line must raise, not silently pass.
    try:
        site_fonts.inject('<head></head>', on=True)
    except RuntimeError:
        pass
    else:
        FAILS.append('inject() did not raise when no Google Fonts line was present')

    # 5. Live templates: every page that ships must keep its size-adjust fallback, or the
    #    font swap reflows (this is the CLS trap the rollout can reintroduce).
    for rel in ('index.html', 'templates/restaurant.html'):
        p = os.path.join(REPO, rel)
        if not os.path.isfile(p):
            continue
        html = open(p).read()
        check('size-adjust' in html, f'{rel}: no size-adjust fallback — font swap will shift layout')
        if rel == 'index.html':
            check('fonts.googleapis.com' not in html,
                  'index.html still loads Google Fonts (homepage rollout incomplete)')
            check('<style id="site-fonts">' in html, 'index.html has no self-hosted @font-face block')

    if FAILS:
        print('FAIL')
        for f in FAILS:
            print('  -', f)
        return 1
    print('PASS: self-hosted fonts guards')
    return 0


if __name__ == '__main__':
    sys.exit(main())
