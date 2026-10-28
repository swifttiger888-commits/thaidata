#!/usr/bin/env python3
"""Tests for festival page generation: past-event labelling + JSON-LD filtering."""

import json
import re
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import generate_festival_pages as gen  # noqa: E402

TODAY = date(2026, 9, 7)


def _ev(**kw):
    e = {
        "event_id": "t1", "event_name": "Test", "start_date": None,
        "end_date": None, "date_description": "TBC", "tags": [],
        "ticket_info": None, "description": "d", "status": "tbc",
        "venue_name": "V", "address": None, "organiser": None,
    }
    e.update(kw)
    return e


def test_is_past():
    assert gen.is_past(_ev(end_date="2026-04-13"), today=TODAY)
    assert gen.is_past(_ev(start_date="2026-04-13"), today=TODAY)
    assert not gen.is_past(_ev(start_date="2026-11-15"), today=TODAY)
    assert not gen.is_past(_ev(start_date="2026-09-07"), today=TODAY)  # today = not past
    assert not gen.is_past(_ev(start_date=None), today=TODAY)
    assert not gen.is_past(_ev(start_date="bogus"), today=TODAY)


def test_past_card_gets_ended_badge():
    html = gen.event_card_html(_ev(event_name="Old Event", start_date="2026-04-13",
                                   end_date="2026-04-13", date_description="13"))
    assert 'class="event-card event-past"' in html
    assert '<span class="ev-ended">Ended</span>' in html

    html = gen.event_card_html(_ev(event_name="Future Event", start_date="2026-11-15",
                                   end_date="2026-11-15", date_description="15"))
    assert 'class="event-card">' in html
    assert "ev-ended" not in html


def test_ld_json_omits_past():
    events = [
        _ev(event_id="past1", event_name="Past", start_date="2026-04-13",
            end_date="2026-04-13", status="confirmed"),
        _ev(event_id="future1", event_name="Future", start_date="2026-11-15",
            end_date="2026-11-15", status="estimated"),
    ]
    schema = json.loads(gen.generate_ld_json(events))
    names = [i["item"]["name"] for i in schema["itemListElement"]]
    assert names == ["Future"]


def test_calendar_page_badges_and_anchors():
    events = [
        _ev(event_id="songkran-wat-buddhapadipa-2026", event_name="Songkran at Wat Buddhapadipa",
            start_date="2026-04-11", end_date="2026-04-12", date_description="11–12 April 2026",
            status="confirmed"),
    ]
    html = gen.gen_calendar_page(events)
    assert "Songkran at Wat Buddhapadipa<span class=\"ev-ended\">Ended</span>" in html
    assert 'id="april"' in html  # month anchors preserved
    assert "kept for reference" in html  # intro copy explains Ended


def test_songkran_page_ended_note():
    events = [
        _ev(event_id="songkran-wat-buddhapadipa-2026", festival_type="songkran",
            event_name="Songkran Wat B", city="London", venue_name="Wat B",
            start_date="2026-04-11", end_date="2026-04-12", status="confirmed"),
    ]
    html = gen.gen_songkran_page(events)
    assert "The 2026 celebrations have now ended" in html
    assert "Next: 13–15 April 2027" in html


# ── Date badge ───────────────────────────────────────────────────────────────
# The badge is an 88px column at 2.4rem. `date_description` is free text and was
# being dropped straight into it, so "1 November 2026" rendered at 38px and printed
# over the card description and tags; and MONTH_ABBR only covered Apr–Dec, so the
# two 2027 events (Jan 9, Mar 13) printed a literal "???" as their month.

def test_day_badge_derives_from_iso_dates_not_free_text():
    label, cls = gen.day_badge(_ev(start_date="2026-04-11", end_date="2026-04-12",
                                   date_description="11-12 April 2026"))
    assert label == "11\u201312"
    assert cls == "day--range"

    label, cls = gen.day_badge(_ev(start_date="2026-11-01", end_date="2026-11-01",
                                   date_description="1 November 2026"))
    assert label == "1" and cls == "day--single"


def test_day_badge_keeps_the_estimate_asterisk():
    label, _ = gen.day_badge(_ev(start_date="2026-04-12", end_date="2026-04-13",
                                 date_description="12-13*"))
    assert label.endswith("*") and label.startswith("12")


def test_day_badge_is_tbc_without_a_date():
    assert gen.day_badge(_ev()) == ("TBC", "day--tbc")


def test_day_badge_never_spans_months():
    # 28 Jun -> 2 Jul must not claim a range inside June.
    label, cls = gen.day_badge(_ev(start_date="2026-06-28", end_date="2026-07-02"))
    assert label == "28" and cls == "day--single"


def test_month_abbr_covers_every_month():
    assert sorted(gen.MONTH_ABBR) == list(range(1, 13))
    assert not any("?" in v for v in gen.MONTH_ABBR.values())


def test_generated_pages_have_no_placeholder_or_overflowing_badges():
    pages = [REPO / "thai-festivals-uk.html", REPO / "loy-krathong-uk.html"]
    seen = 0
    for page in pages:
        if not page.exists():
            continue
        html = page.read_text(encoding="utf-8")
        assert "???" not in html, page.name
        for cls, text in re.findall(
                r'<div class="day (day--\w+)">([^<]*)</div>', html):
            seen += 1
            assert len(text) <= 6, (page.name, text)
            if cls == "day--tbc":
                assert text == "TBC"
            else:
                assert re.fullmatch(r"\d{1,2}(\u2013\d{1,2})?\*?", text), (page.name, text)
    assert seen > 20, seen


# ── Analytics + consent ──────────────────────────────────────────────────────
# These three pages carried neither the GA4 tag nor the cookie banner, so the two
# biggest traffic drivers (festival hub + Loy Krathong: 74 of 319 clicks in 28 days)
# were invisible in GA4 and collected nothing under a consent mechanism. The banner
# must ship in the same change as the tag — analytics without a way to consent is
# the failure mode, not the fix.

FESTIVAL_PAGES = ["thai-festivals-uk.html", "songkran-uk.html", "loy-krathong-uk.html"]


def test_generator_carries_the_analytics_and_banner_constants():
    assert "G-B6RYQZX5QX" in gen.ANALYTICS_HEAD
    assert "consent" in gen.ANALYTICS_HEAD
    assert "/privacy-banner.js" in gen.CONSENT_BANNER


def test_every_festival_page_has_ga4_and_the_consent_banner():
    for name in FESTIVAL_PAGES:
        page = REPO / name
        assert page.exists(), name
        html = page.read_text(encoding="utf-8")
        assert "G-B6RYQZX5QX" in html, name
        assert 'gtag(\'consent\', \'default\'' in html, name
        assert "/privacy-banner.js" in html, name


def test_consent_banner_sits_before_the_closing_body():
    for name in FESTIVAL_PAGES:
        html = (REPO / name).read_text(encoding="utf-8")
        assert html.index("/privacy-banner.js") < html.index("</body>"), name
