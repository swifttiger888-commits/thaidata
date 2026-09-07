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
