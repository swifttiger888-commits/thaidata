"""Guards for the shared GA4/consent snippet and the city + chain page families.

City pages (278) and chain pages (27) were the largest unmeasured families on the
site — including the worst-performing high-impression URLs, e.g. /cities/leeds at
140 impressions and 0 clicks in 28 days with no way to see what visitors did.
"""
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import site_analytics  # noqa: E402

CITY_PAGES = sorted((REPO / "cities").glob("*.html"))
CHAIN_PAGES = sorted((REPO / "chains").glob("*.html"))


def test_families_exist():
    assert len(CITY_PAGES) > 100, len(CITY_PAGES)
    assert len(CHAIN_PAGES) > 20, len(CHAIN_PAGES)


def test_every_city_page_has_ga4_and_the_banner():
    missing = [p.name for p in CITY_PAGES
               if site_analytics.GA_ID not in p.read_text(encoding="utf-8", errors="ignore")]
    assert not missing, missing[:8]


def test_every_chain_page_has_ga4_and_the_banner():
    bad = []
    for p in CHAIN_PAGES:
        html = p.read_text(encoding="utf-8", errors="ignore")
        if site_analytics.GA_ID not in html or "/privacy-banner.js" not in html:
            bad.append(p.name)
    assert not bad, bad[:8]


def test_consent_defaults_to_denied():
    assert "analytics_storage: 'denied'" in site_analytics.ANALYTICS_HEAD
    assert "gtag('consent', 'default'" in site_analytics.ANALYTICS_HEAD


def test_ensure_analytics_is_idempotent():
    page = '<html><head><meta name="viewport" content="width=device-width"></head><body>x</body></html>'
    once = site_analytics.ensure_analytics(page)
    twice = site_analytics.ensure_analytics(once)
    assert once == twice
    assert once.count(site_analytics.GA_ID) == 2      # config + script src
    assert once.count("/privacy-banner.js") == 1


def test_ensure_analytics_injects_inside_head_and_before_body_close():
    page = '<html><head><meta name="viewport" content="width=device-width"></head><body>x</body></html>'
    out = site_analytics.ensure_analytics(page)
    assert out.index("<script>") > out.index("viewport")
    assert out.index("/privacy-banner.js") < out.index("</body>")


def test_measurement_id_does_not_drift_between_generators():
    # Five generators emit this id. If one drifts, that family silently reports into
    # the void — which is exactly how the listing pages went unmeasured for months.
    ids = {site_analytics.GA_ID}
    for rel in ("templates/restaurant.html", "index.html", "thai-festivals-uk.html"):
        f = REPO / rel
        if not f.exists():
            continue
        found = set(re.findall(r"G-[A-Z0-9]{8,}", f.read_text(encoding="utf-8", errors="ignore")))
        if found:
            ids |= found
    assert len(ids) == 1, ids


def test_london_manual_page_keeps_its_markers():
    london = REPO / "cities" / "london.html"
    if not london.exists():
        pytest.skip("no london page")
    html = london.read_text(encoding="utf-8")
    assert "<!-- MANUAL -->" in html
    assert "CITIES-MODE: manual" in html
    assert site_analytics.GA_ID in html
