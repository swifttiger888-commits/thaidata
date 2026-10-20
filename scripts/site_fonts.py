"""Self-hosted webfonts for ThaiData pages.

Why: Google Fonts adds two extra origins to the critical path (fonts.googleapis.com
CSS -> fonts.gstatic.com woff2). Under Lighthouse's mobile simulation that chain is
~1.2 s of LCP; self-hosting the same files inlines the @font-face rules and removes
both origins. See .hermes/audits for the measured A/B.

Rollout is flag-gated: set SELF_HOST_FONTS=1 when building generators to emit the
self-hosted block. With the flag unset the generators emit exactly what they did
before (Google Fonts), so a bad rollout is reverted by unsetting it.

Files in /assets/fonts are the latin + latin-ext subsets of Google's own woff2,
copied verbatim (OFL-licensed), so rendering is identical to the hosted version.
Filenames are version-suffixed because _headers serves *.woff2 as immutable for a year.
"""
from __future__ import annotations

import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(REPO, 'assets', 'fonts')

# Variable Archivo (wght 500-800) + variable Inter (opsz 14-32, wght 100-900),
# latin and latin-ext only. Copied from the Google Fonts CSS response, URLs rewritten.
FONT_FACE_CSS = """@font-face { font-family: 'Archivo'; font-style: normal; font-weight: 500 800; font-stretch: 100%; font-display: swap; src: url(/assets/fonts/archivo-latin-ext-v1.woff2) format('woff2'); unicode-range: U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C4, U+2113, U+2C60-2C7F, U+A720-A7FF; }
@font-face { font-family: 'Archivo'; font-style: normal; font-weight: 500 800; font-stretch: 100%; font-display: swap; src: url(/assets/fonts/archivo-latin-v1.woff2) format('woff2'); unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD; }
@font-face { font-family: 'Inter'; font-style: normal; font-weight: 100 900; font-display: swap; src: url(/assets/fonts/inter-latin-ext-v1.woff2) format('woff2'); unicode-range: U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C4, U+2113, U+2C60-2C7F, U+A720-A7FF; }
@font-face { font-family: 'Inter'; font-style: normal; font-weight: 100 900; font-display: swap; src: url(/assets/fonts/inter-latin-v1.woff2) format('woff2'); unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD; }
"""

# Preload only the face that paints the LCP text (H1 is Archivo). Preloading every
# face competes with the document on a throttled mobile connection.
PRELOAD = ('archivo-latin-v1.woff2',)

REQUIRED_ASSETS = (
    'archivo-latin-v1.woff2',
    'archivo-latin-ext-v1.woff2',
    'inter-latin-v1.woff2',
    'inter-latin-ext-v1.woff2',
)


def enabled() -> bool:
    """Default ON. SELF_HOST_FONTS=0 reverts generated pages to Google Fonts.

    Default-on on purpose: the generated HTML is committed, so a flag that defaults off
    would silently revert 1,266 pages to Google Fonts the next time someone regenerates
    without setting it. Reverting is a deliberate act, not an omission.
    """
    return os.environ.get('SELF_HOST_FONTS', '1').strip().lower() not in ('0', 'false', 'no', 'off')


def missing_assets() -> list[str]:
    return [f for f in REQUIRED_ASSETS if not os.path.isfile(os.path.join(FONT_DIR, f))]


def head_block(indent: str = '') -> str:
    """Preload + inline @font-face rules, indented for the surrounding <head>."""
    missing = missing_assets()
    if missing:
        raise FileNotFoundError(f'self-hosted fonts missing from {FONT_DIR}: {missing}')
    lines = []
    for f in PRELOAD:
        lines.append(
            f'<link rel="preload" href="/assets/fonts/{f}" as="font" type="font/woff2" crossorigin />'
        )
    lines.append('<style id="site-fonts">')
    lines.append(FONT_FACE_CSS)
    lines.append('</style>')
    return '\n'.join(indent + line for line in lines)


# Any line mentioning these is part of the Google Fonts delivery path (link, noscript,
# preconnect) and is replaced by head_block() when the flag is on.
_GOOGLE_MARKERS = ('fonts.googleapis.com', 'fonts.gstatic.com')


def inject(html: str, *, on: bool | None = None) -> str:
    """Replace the Google Fonts <link>/preconnect/noscript lines with the self-hosted block.

    With the flag off the html is returned untouched. Raises if no Google Fonts line was
    found when the flag is on — that means the template changed and the swap silently
    stopped applying, which would leave the page on Google Fonts while we think otherwise.
    """
    if on is None:
        on = enabled()
    if not on:
        return html

    out: list[str] = []
    inserted = False
    for line in html.split('\n'):
        if any(m in line for m in _GOOGLE_MARKERS):
            if not inserted:
                indent = line[: len(line) - len(line.lstrip())]
                out.append(head_block(indent))
                inserted = True
            continue
        out.append(line)

    if not inserted:
        raise RuntimeError('no Google Fonts <link> found to replace — template changed?')
    return '\n'.join(out)


if __name__ == '__main__':
    print('enabled:', enabled(), 'missing:', missing_assets())
    print(head_block()[:400])
