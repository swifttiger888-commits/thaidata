"""Guards for the menu-page analytics, consent and error-report surface.

Menu pages were the last unmeasured family on the site: 166 built pages, zero GA4
and zero consent mechanism, while they carried thousands of impressions a month.
They also publish extracted dish names and prices with no feedback path if one is
wrong — and a wrong dish has already been found in the wild.
"""
import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import build_menu_page as gen  # noqa: E402

MENU_PAGES = sorted(REPO.glob("r/*/*/menu/index.html"))


def test_menu_pages_exist():
    assert len(MENU_PAGES) > 100, len(MENU_PAGES)


def test_every_menu_page_has_ga4_and_the_consent_banner():
    missing_ga, missing_banner = [], []
    for p in MENU_PAGES:
        html = p.read_text(encoding="utf-8", errors="ignore")
        if "G-B6RYQZX5QX" not in html:
            missing_ga.append(str(p.relative_to(REPO)))
        if "/privacy-banner.js" not in html:
            missing_banner.append(str(p.relative_to(REPO)))
    assert not missing_ga, missing_ga[:5]
    assert not missing_banner, missing_banner[:5]


def test_consent_defaults_to_denied():
    assert "analytics_storage: 'denied'" in gen.ANALYTICS_HEAD
    assert "gtag('consent', 'default'" in gen.ANALYTICS_HEAD
    assert gen.GA_ID in gen.ANALYTICS_HEAD


def test_banner_loads_before_the_closing_body_tag():
    for p in MENU_PAGES[:20]:
        html = p.read_text(encoding="utf-8", errors="ignore")
        assert html.index("/privacy-banner.js") < html.index("</body>"), p


def test_every_menu_page_has_the_report_form():
    missing = [str(p.relative_to(REPO)) for p in MENU_PAGES
               if 'id="report-form"' not in p.read_text(encoding="utf-8", errors="ignore")]
    assert not missing, missing[:5]


def test_report_form_carries_the_restaurant_context():
    p = REPO / "r" / "leeds" / "thai-aroy-dee" / "menu" / "index.html"
    if not p.exists():
        pytest.skip("sample page not built")
    m = re.search(r'<section class="report"[^>]*>', p.read_text(encoding="utf-8"))
    assert m, "report section missing"
    tag = m.group(0)
    for attr in ("data-name", "data-city", "data-fsa"):
        assert attr in tag, attr
    assert 'data-city="Leeds"' in tag


def test_report_posts_the_menu_category():
    # 'menu' is already in ALLOWED_CATEGORIES on functions/api/correction.js — if it
    # ever leaves that list, every menu correction silently 400s.
    body = (REPO / "functions" / "api" / "correction.js").read_text(encoding="utf-8")
    m = re.search(r"ALLOWED_CATEGORIES = \[([^\]]*)\]", body)
    assert m, "ALLOWED_CATEGORIES not found"
    assert "'menu'" in m.group(1)
    assert "category: 'menu'" in gen.REPORT_BODY


def test_report_form_has_a_honeypot():
    assert 'name="website"' in gen.REPORT_BODY
    assert "report-hp" in gen.REPORT_BODY


def test_report_js_has_no_template_placeholders_left():
    # The page template is an f-string; a stray single brace in REPORT_BODY would be
    # consumed at build time and silently vanish.
    for page in MENU_PAGES[:10]:
        html = page.read_text(encoding="utf-8", errors="ignore")
        assert "{REPORT_BODY}" not in html
        assert "{ANALYTICS_HEAD}" not in html
        assert "{CONSENT_BANNER}" not in html
