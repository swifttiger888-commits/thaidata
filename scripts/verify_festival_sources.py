#!/usr/bin/env python3
"""Verify null source_url/source_type in thai_festivals.json.
Fills from known-good lookup table. Never overrides non-null.
No scraping, no network calls, no page generation changes.
"""

import json, sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA_FILE = REPO / "data" / "thai_festivals.json"

# Lookup: entries where the source URL is clearly valid
# for the specific event instance, not just the festival type.
# Entries to strip (remove invalid auto-fill sources from prior runs)
STRIP = {"kings-birthday-2026", "nye-temple-ceremonies-2026"}

LOOKUP = [
    # Magic of Thailand tour — all city stops route through the same
    # official tour organiser site, referenced in the existing HTML
    {"id": "magic-of-thailand-wimbledon-2026",         "url": "https://magicofthailand.co.uk", "type": "venue",       "conf": 0.85, "note": "Source from tour organiser website magicofthailand.co.uk, referenced in existing HTML"},
    {"id": "magic-of-thailand-poole-2026",             "url": "https://magicofthailand.co.uk", "type": "venue",       "conf": 0.85, "note": "Source from tour organiser website magicofthailand.co.uk, referenced in existing HTML"},
    {"id": "magic-of-thailand-maidstone-2026",         "url": "https://magicofthailand.co.uk", "type": "venue",       "conf": 0.85, "note": "Source from tour organiser website magicofthailand.co.uk, referenced in existing HTML"},
    {"id": "magic-of-thailand-basingstoke-2026",       "url": "https://magicofthailand.co.uk", "type": "venue",       "conf": 0.85, "note": "Source from tour organiser website magicofthailand.co.uk, referenced in existing HTML"},
    {"id": "magic-of-thailand-nottingham-2026",        "url": "https://magicofthailand.co.uk", "type": "venue",       "conf": 0.85, "note": "Source from tour organiser website magicofthailand.co.uk, referenced in existing HTML"},
    {"id": "magic-of-thailand-manchester-2026",        "url": "https://magicofthailand.co.uk", "type": "venue",       "conf": 0.85, "note": "Source from tour organiser website magicofthailand.co.uk, referenced in existing HTML"},
    {"id": "magic-of-thailand-warwick-portsmouth-2026","url": "https://magicofthailand.co.uk", "type": "venue",      "conf": 0.85, "note": "Source from tour organiser website magicofthailand.co.uk, referenced in existing HTML"},
    {"id": "magic-of-thailand-ealing-2026",            "url": "https://magicofthailand.co.uk", "type": "venue",       "conf": 0.85, "note": "Source from tour organiser website magicofthailand.co.uk, referenced in existing HTML"},
    # Southampton Thai Festival — organiser website explicit in existing HTML
    {"id": "southampton-thai-festival-2026",           "url": "https://southamptonthaifestival.com", "type": "venue",    "conf": 0.85, "note": "Source from organiser website southamptonthaifestival.com, referenced in existing HTML"},
    # Thailand Showcase — Royal Thai Embassy London, the official organiser
    {"id": "thailand-showcase-2026",                   "url": "https://london.thaiembassy.org", "type": "embassy",      "conf": 0.85, "note": "Source from Royal Thai Embassy London website — organiser of the annual Thailand Showcase event"},
]

TODAY = date.today().isoformat()


def verify():
    with open(DATA_FILE) as f:
        data = json.load(f)

    stripped = 0
    for ev in data["events"]:
        if ev["event_id"] in STRIP and ev.get("source_url") is not None:
            ev["source_url"] = None
            ev["source_type"] = None
            ev["confidence"] = 0.40
            ev["notes"] = (ev.get("notes") or "") + f"\n[cleaned {TODAY}] Removed auto-filled source — does not verify the specific event instance"
            ev["updated_at"] = TODAY
            stripped += 1
    if stripped:
        print(f"Stripped:    {stripped}")

    changed = 0
    for entry in LOOKUP:
        eid = entry["id"]
        match = None
        for ev in data["events"]:
            if ev["event_id"] == eid:
                match = ev
                break
        if not match:
            print(f"  SKIP  no event found: {eid}")
            continue

        # Never override non-null source_url
        if match.get("source_url") is not None:
            continue

        match["source_url"] = entry["url"]
        match["source_type"] = entry["type"]
        prev_conf = match.get("confidence", 0.0)
        if entry["conf"] > prev_conf:
            match["confidence"] = entry["conf"]
        existing_note = match.get("notes") or ""
        verify_note = f"[verified {TODAY}] {entry['note']}"
        if existing_note:
            match["notes"] = existing_note + "\n" + verify_note
        else:
            match["notes"] = verify_note
        match["updated_at"] = TODAY
        changed += 1

    if stripped or changed:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")

    total = len(data["events"])
    null_source = sum(1 for e in data["events"] if e.get("source_url") is None)
    print(f"Total events: {total}")
    print(f"Auto-filled:  {changed}")
    print(f"Still null:   {null_source}")
    if null_source:
        print("\nManual verification needed for:")
        for ev in data["events"]:
            if ev.get("source_url") is None:
                print(f"  {ev['event_id']}")


if __name__ == "__main__":
    verify()
