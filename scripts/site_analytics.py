"""Single source of truth for the site's GA4 + consent snippet.

Every generated page family needs the same two things: consent-mode v2 with storage
denied by default (tag loaded on first real interaction or after 8s), and
/privacy-banner.js, which upgrades consent when a visitor accepts.

They ship together. Analytics without a consent route is the bug, not the fix, so
do not add the tag to a family that has no banner.

Keeping the id and the snippet in one module stops the five generators drifting
apart — a changed measurement id must not leave a page family reporting into the
void.
"""
import re

GA_ID = "G-B6RYQZX5QX"

ANALYTICS_HEAD = """  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('consent', 'default', { analytics_storage: 'denied', ad_storage: 'denied' });
    gtag('js', new Date());
    gtag('config', '%s');
    (function () {
      var loaded = false;
      function loadGtag() {
        if (loaded) return;
        loaded = true;
        var s = document.createElement('script');
        s.async = true;
        s.src = 'https://www.googletagmanager.com/gtag/js?id=%s';
        document.head.appendChild(s);
      }
      ['pointerdown', 'keydown', 'touchstart', 'wheel'].forEach(function (ev) {
        window.addEventListener(ev, loadGtag, { once: true, passive: true });
      });
      setTimeout(loadGtag, 8000);
    })();
  </script>
""" % (GA_ID, GA_ID)

CONSENT_BANNER = '  <script src="/privacy-banner.js" defer></script>\n'

_VIEWPORT = re.compile(r'(<meta\s+name="viewport"[^>]*>)', re.IGNORECASE)


def ensure_analytics(html: str) -> str:
    """Inject GA4 + the consent banner into a page, idempotently.

    Needed because most generators reuse an existing page verbatim and only fall
    back to a template for new output, so a template edit never reaches pages that
    already exist.
    """
    if GA_ID not in html:
        match = _VIEWPORT.search(html)
        if match:
            html = html[:match.end()] + "\n" + ANALYTICS_HEAD + html[match.end():]
        else:
            head = re.search(r'<head[^>]*>', html, re.IGNORECASE)
            if head:
                html = html[:head.end()] + "\n" + ANALYTICS_HEAD + html[head.end():]
    if "/privacy-banner.js" not in html and "</body>" in html:
        html = html.replace("</body>", CONSENT_BANNER + "</body>", 1)
    return html
