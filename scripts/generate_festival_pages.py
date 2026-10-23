#!/usr/bin/env python3
"""Generate festival HTML pages from data/thai_festivals.json.
Preserves all editorial content, cross-links, anchors, and LD+JSON schema.
"""

import json
from datetime import datetime
from pathlib import Path
import site_icons  # noqa: E402  (same-dir module, replaces Font Awesome)

REPO = Path(__file__).resolve().parent.parent
DATA_FILE = REPO / "data" / "thai_festivals.json"

# ── Helpers ──────────────────────────────────────────────────────────────

MONTH_ABBR = {4: "Apr", 5: "May", 6: "Jun", 7: "Jul",
              8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}

MONTH_ANCHOR = {
    "april": ("April — Songkran (Thai New Year) 🎉", 4),
    "may": ("May — Festival Season Begins", 5),
    "june": ("June — Embassy + More Festivals", 6),
    "july": ("July — Mid-Summer Festivals", 7),
    "august": ("August — Summer Festivals Continue", 8),
    "september": ("September — Tour Finale", 9),
    "october": ("October — Kathina & Vegetarian Festival", 10),
    "november": ("November — Loy Krathong 🏮", 11),
    "december": ("December — Year-End Celebrations", 12),
}

# event_id → month anchor for events without a start_date
NULL_DATE_MONTH = {
    "songkran-scotland-2026": None,  # only in songkran page
    "thailand-showcase-2026": "june",
    "magic-of-thailand-basingstoke-2026": "june",
    "magic-of-thailand-nottingham-2026": "july",
    "magic-of-thailand-warwick-portsmouth-2026": "august",
    "kathina-2026": "october",
    "vegetarian-festival-2026": "october",
    "loy-krathong-wat-phra-singh-2026": "november",
    "songkran-wat-buddharam-2027": "april",
    "loy-krathong-wat-buddharam-2027": "november",
    "songkran-wat-phra-srisanphet-2027": "april",
}

# special ordering within each month
EVENT_ORDER = [
    "songkran-wat-buddhapadipa-2026",
    "songkran-wat-phra-singh-2026",
    "songkran-wat-charoenbhavana-2026",
    "songkran-wat-mahathat-2026",
    "songkran-wat-sanghapadipa-2026",
    "magic-of-thailand-wimbledon-2026",
    "magic-of-thailand-poole-2026",
    "magic-of-thailand-maidstone-2026",
    "thailand-showcase-2026",
    "magic-of-thailand-basingstoke-2026",
    "southampton-thai-festival-2026",
    "magic-of-thailand-nottingham-2026",
    "magic-of-thailand-manchester-2026",
    "magic-of-thailand-warwick-portsmouth-2026",
    "magic-of-thailand-ealing-2026",
    "kathina-2026",
    "vegetarian-festival-2026",
    "alms-giving-end-vassa-wat-buddhapadipa-2026",
    "loy-krathong-wat-mahathat-2026",
    "kathina-loykrathong-wat-phra-srisanphet-2026",
    "kathina-wat-buddhapadipa-2026",
    "loy-krathong-wat-buddhapadipa-2026",
    "kathina-wat-phra-singh-2026",
    "loy-krathong-wat-phra-singh-2026",
    "thai-business-awards-cardiff-2026",
    "thai-business-awards-london-2026",
    "thai-national-day-wat-buddhapadipa-2026",
    "kings-birthday-2026",
    "nye-temple-ceremonies-2026",
]


def load_events():
    with open(DATA_FILE) as f:
        return json.load(f)["events"]


def is_past(e, today=None):
    """True if the event's final day (end_date, else start_date) is before today."""
    if today is None:
        today = datetime.now().date()
    d = e.get("end_date") or e.get("start_date")
    if not d:
        return False
    try:
        return datetime.fromisoformat(d).date() < today
    except ValueError:
        return False


def event_month(e):
    """Return int month (1-12) or None for null-date events."""
    if e["start_date"]:
        return datetime.strptime(e["start_date"], "%Y-%m-%d").month
    anchor = NULL_DATE_MONTH.get(e["event_id"])
    if anchor and anchor in MONTH_ANCHOR:
        return MONTH_ANCHOR[anchor][1]
    return None


def tag_html(tags, ticket_info):
    """Render event-tags div matching current HTML patterns."""
    parts = []
    for t in tags:
        if t == "temple":
            parts.append(("tag-temple", "Temple"))
        elif t == "food_festival":
            parts.append(("tag-food", "Food Festival"))
        elif t == "food":
            parts.append(("tag-food", "Food"))
        elif t == "embassy":
            parts.append(("tag-embassy", "Embassy"))
        elif t == "free_entry":
            parts.append(("tag-free", "Free Entry"))
        elif t == "free":
            if "paid" not in tags and "food_festival" not in tags:
                parts.append(("tag-free", "Free/Low Cost"))
        elif t == "paid":
            if "food_festival" in tags:
                if ticket_info and "6" in ticket_info:
                    label = ticket_info.replace("6 pounds", "\u00a36").replace("pounds", "\u00a3")
                    label = label.strip().title()
                    parts.append(("tag-paid", label if "Tickets" not in label else ticket_info))
                elif ticket_info and "Tickets" in ticket_info:
                    parts.append(("tag-paid", "Tickets TBC"))
                else:
                    parts.append(("tag-paid", "\u00a36 Entry"))
            else:
                parts.append(("tag-paid", "Paid"))
    # deduplicate by label
    seen = set()
    result = []
    for cls, label in parts:
        if label not in seen:
            result.append(f'<span class="ev-tag {cls}">{label}</span>')
            seen.add(label)
    return "".join(result)


def event_card_html(e):
    """Render a single event-card div."""
    if e["start_date"]:
        m = datetime.strptime(e["start_date"], "%Y-%m-%d").month
        month_label = MONTH_ABBR.get(m, "???")
    else:
        month_label = ""
    day_label = e["date_description"] or ""
    loc = e["address"] or e["venue_name"] or ""
    tags = tag_html(e["tags"], e["ticket_info"])
    past = is_past(e)
    past_cls = " event-past" if past else ""
    ended = '<span class="ev-ended">Ended</span>' if past else ""
    return f'''            <div class="event-card{past_cls}">
                <div class="event-date"><div class="month">{month_label}</div><div class="day">{day_label}</div></div>
                <div class="event-info">
                    <div class="ev-title">{e["event_name"]}{ended}</div>
                    <div class="ev-location"><i class="fas fa-map-marker-alt"></i>{loc}</div>
                    <div class="ev-desc">{e["description"]}</div>
                    <div class="event-tags">{tags}</div>
                </div>
            </div>'''


def generate_ld_json(events):
    """Generate inline LD+JSON schema for ItemList with select events.

    Only future events are included — Google ignores past events for rich
    results, and marking past events EventScheduled is inaccurate.
    """
    items = []
    idx = 1
    today = datetime.now().date()
    for e in events:
        if e["status"] == "tbc" or not e["start_date"]:
            continue
        try:
            sd_dt = datetime.fromisoformat(e["start_date"]).date()
        except ValueError:
            continue
        if sd_dt < today:
            continue  # past event — omit from schema
        name = e["event_name"]
        sd = e["start_date"]
        ed = e["end_date"] if e["end_date"] != e["start_date"] else None
        loc_name = e["venue_name"]
        loc_addr = e["address"] or loc_name
        item = {
            "@type": "Event",
            "name": name,
            "startDate": sd,
            "eventStatus": "https://schema.org/EventScheduled",
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
            "description": (e["description"] or "").strip(),
            "location": {"@type": "Place", "name": loc_name, "address": loc_addr}
        }
        if ed:
            item["endDate"] = ed
        org = (e.get("organiser") or "").strip()
        if org:
            item["organizer"] = {"@type": "Organization", "name": org}
        ticket = (e.get("ticket_info") or "").strip().lower()
        if ticket.startswith("free"):
            item["isAccessibleForFree"] = True
        items.append({"@type": "ListItem", "position": idx, "item": item})
        idx += 1
        if idx > 10:
            break
    schema = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "UK Thai Festivals & Cultural Events 2026",
        "description": "Complete calendar of Thai cultural events across the United Kingdom including Songkran, Loy Krathong, food festivals, and temple celebrations.",
        "numberOfItems": len(items),
        "itemListElement": items
    }
    return json.dumps(schema, indent=None)


# ── Page: thai-festivals-uk.html ─────────────────────────────────────────

def gen_calendar_page(events):
    """Full main calendar page with all events."""
    month_order = ["april", "may", "june", "july", "august",
                   "september", "october", "november", "december"]
    grouped = {m: [] for m in month_order}
    ev_map = {e["event_id"]: e for e in events}
    past_events = []
    tbc_events = []
    for eid in EVENT_ORDER:
        e = ev_map.get(eid)
        if not e:
            continue
        if not e.get("start_date"):
            tbc_events.append(e)
            continue
        if is_past(e):
            past_events.append(e)
            continue
        m = event_month(e)
        if m is None:
            continue
        for anchor, (_, mth) in MONTH_ANCHOR.items():
            if mth == m:
                grouped[anchor].append(e)
                break
    # Build calendar HTML
    calendar_html = ""
    for anchor in month_order:
        evs = grouped[anchor]
        if not evs:
            continue
        header_label = MONTH_ANCHOR[anchor][0]
        calendar_html += f'\n            <!-- {header_label.split(" —")[0].upper()} -->\n'
        calendar_html += f'            <div class="month-header" id="{anchor}">{header_label}</div>\n'
        for e in evs:
            calendar_html += event_card_html(e) + "\n"
    if past_events:
        calendar_html += '\n            <!-- EARLIER IN 2026 -->\n'
        calendar_html += '            <div class="month-header" id="earlier-2026">Earlier in 2026 — ended</div>\n'
        past_grouped = {}
        for e in past_events:
            m = event_month(e)
            if m is None:
                continue
            for anchor, (_, mth) in MONTH_ANCHOR.items():
                if mth == m:
                    past_grouped.setdefault(anchor, []).append(e)
                    break
        for anchor in month_order:
            pevs = past_grouped.get(anchor) or []
            if not pevs:
                continue
            header_id = anchor if f'id="{anchor}"' not in calendar_html else f"{anchor}-past"
            calendar_html += f'            <div class="month-header" id="{header_id}" style="opacity:0.75;font-size:0.95rem;">{MONTH_ANCHOR[anchor][0]}</div>\n'
            for e in pevs:
                calendar_html += event_card_html(e) + "\n"
    if tbc_events:
        calendar_html += '\n            <!-- DATES TO BE CONFIRMED -->\n'
        calendar_html += '            <div class="month-header" id="dates-tbc">Dates to be confirmed</div>\n'
        for e in tbc_events:
            calendar_html += event_card_html(e) + "\n"

    ld_json = generate_ld_json(events)

    return f'''<!DOCTYPE html>
<html lang="en-GB">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Thai Festivals UK 2026: Calendar & Events | ThaiData</title>
    <meta name="description" content="The only complete UK Thai events calendar. Songkran, Loy Krathong, food festivals, temple celebrations — every Thai cultural event across the UK, all in.">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="https://thaidata.uk/thai-festivals-uk">

    <meta property="og:type" content="website">
    <meta property="og:url" content="https://thaidata.uk/thai-festivals-uk">
    <meta property="og:title" content="Thai Festivals UK 2026: Complete Calendar & Temple Events">
    <meta property="og:description" content="Every Thai cultural event across the UK — Songkran, Loy Krathong, food festivals, temple celebrations. Filter by city, date, or event type.">
    <meta property="og:image" content="https://thaidata.uk/thaidataukhero.webp">
    <meta property="og:locale" content="en_GB">

    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Thai Festivals UK 2026: Complete Calendar & Temple Events">
    <meta name="twitter:description" content="Every Thai cultural event across the UK — Songkran, Loy Krathong, food festivals, temple celebrations. Filter by city, date, or event type.">
    <meta name="twitter:image" content="https://thaidata.uk/thaidataukhero.webp">

    <script type="application/ld+json">
    {ld_json}
    </script>
    <script type="application/ld+json">
{{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{{"@type":"ListItem","position":1,"name":"Home","item":"https://thaidata.uk/"}},{{"@type":"ListItem","position":2,"name":"Guides","item":"https://thaidata.uk/guides"}},{{"@type":"ListItem","position":3,"name":"Thai Festivals UK 2026: Calendar & Events"}}]}}
    </script>

    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" media="print" onload="this.media='all'"><noscript><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" /></noscript>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet" media="print" onload="this.media='all'" /><noscript><link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet" /></noscript>
    <style>
        :root {{
            --c1: #A3132B; --c2: #A3132B; --dark: #FFFFFF; --ink: #1A1614; --ink2: #4A403C; --ink3: #7A6F6A; --ink4: #9C918C; --line: #E7DFD5; --bg: #FBF7F0; --gold: #F59E0B; --pink: #EC4899;
        }}
:focus-visible {{
            outline: 2px solid #10B981;
            outline-offset: 2px;
            border-radius: 4px;
        }}
        :focus:not(:focus-visible) {{
            outline: none;
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    img, svg, video, canvas {{
      max-width: 100%;
      height: auto
    }}
                html {{ overflow-x: hidden; }}
body {{ font-family: 'Inter', system-ui, sans-serif; color: var(--ink); background: var(--bg); line-height: 1.6; -webkit-font-smoothing: antialiased;;
      overflow-x: hidden
    }}
        .grain {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: url("/assets/noise.svg"); opacity: 0.03; pointer-events: none; z-index: 999; }}
        .wrap {{ max-width: 1100px; margin: 0 auto; padding: 0 20px; }}

        nav {{ background: var(--dark); border-bottom: 1px solid var(--line); height: 72px; display: flex; align-items: center; position: sticky; top: 0; z-index: 100; }}
        .nav-bar {{ max-width: 1100px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; padding: 0 20px; width: 100%; }}
        .logo {{ display: flex; align-items: center; gap: 14px; font-weight: 700; font-size: 1.5rem; color: var(--ink); text-decoration: none; }}
        .logo-icon {{ height: 40px; width: auto; display: inline-block; }}

        .header-section {{ padding: 80px 0 60px; text-align: center; position: relative; }}
        .header-section::before {{ content: ''; position: absolute; top: 50%; left: 50%; width: 600px; height: 600px; background: radial-gradient(circle, rgba(16,185,129,0.06) 0%, transparent 70%); transform: translate(-50%, -50%); pointer-events: none; }}
        .header-section h1 {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: clamp(2.5rem, 7vw, 3.8rem); font-weight: 800; line-height: 1.15; margin-bottom: 20px; position: relative; }}
        .header-section h1 em {{ font-style: normal; color: var(--c2); }}
        .header-section p {{ color: var(--ink4); font-size: 1.15rem; max-width: 650px; margin: 0 auto; position: relative; }}

        .section {{ padding: 30px 0 60px; }}
        .section h2 {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: 2rem; font-weight: 800; margin-bottom: 12px; }}
        .section h2 em {{ font-style: normal; color: var(--c2); }}
        .section h3 {{ font-size: 1.1rem; font-weight: 600; margin: 24px 0 10px; }}

        /* Event Cards */
        .event-card {{ background: #FFFFFF; border: 1px solid var(--line); border-radius: 16px; padding: 24px 28px; margin: 14px 0; display: flex; gap: 20px; align-items: flex-start; transition: border-color 0.2s; }}
        .event-card:hover {{ border-color: var(--c2); }}
        .event-date {{ flex-shrink: 0; width: 80px; text-align: center; }}
        .event-date .month {{ font-size: 0.75rem; font-weight: 700; text-transform: uppercase; color: var(--c2); letter-spacing: 0.1em; }}
        .event-date .day {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: 2.4rem; line-height: 1; color: var(--ink); font-weight: 800;}}
        .event-info {{ flex: 1; }}
        .event-info .ev-title {{ font-weight: 700; font-size: 1.05rem; margin-bottom: 4px; }}
        .event-info .ev-location {{ color: var(--ink3); font-size: 0.85rem; margin-bottom: 4px; }}
        .event-info .ev-location i {{ margin-right: 6px; color: var(--ink4); }}
        .event-info .ev-desc {{ color: var(--ink4); font-size: 0.85rem; line-height: 1.6; }}
        .event-tags {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }}
        .ev-tag {{ font-size: 0.68rem; padding: 4px 10px; border-radius: 20px; font-weight: 600; letter-spacing: 0.03em; }}
        .tag-temple {{ background: rgba(139,92,246,0.15); color: #A78BFA; }}
        .tag-food {{ background: rgba(245,158,11,0.15); color: var(--gold); }}
        .tag-embassy {{ background: rgba(16,185,129,0.15); color: var(--c2); }}
        .tag-free {{ background: rgba(34,197,94,0.15); color: #22C55E; }}
        .tag-paid {{ background: rgba(236,72,153,0.15); color: var(--pink); }}

        /* Past events */
        .event-card.event-past {{ opacity: 0.55; }}
        .event-card.event-past:hover {{ opacity: 0.85; }}
        .ev-ended {{ display: inline-block; font-size: 0.62rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; padding: 3px 9px; border-radius: 20px; background: rgba(148,163,184,0.14); color: var(--ink3); margin-left: 8px; vertical-align: 2px; }}

        /* Month headers */
        .month-header {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: 1.8rem; color: var(--c2); padding: 30px 0 10px; border-top: 1px solid var(--line); margin-top: 10px; font-weight: 800;}}

        /* Temple Directory */
        .temple-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 14px; margin-top: 20px; }}
        .temple-card {{ background: #FFFFFF; border: 1px solid var(--line); border-radius: 14px; padding: 20px; }}
        .temple-card .t-name {{ font-weight: 700; font-size: 0.95rem; margin-bottom: 6px; }}
        .temple-card .t-name .thai {{ color: var(--c2); font-weight: 400; font-size: 0.85rem; display: block; margin-top: 2px; }}
        .temple-card .t-loc {{ color: var(--ink4); font-size: 0.82rem; }}
        .temple-card .t-loc i {{ margin-right: 6px; }}
        .temple-card .t-events {{ color: var(--ink3); font-size: 0.8rem; margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--line); }}

        .cta-box {{ text-align: center; padding: 60px 0; }}
        .cta-box a {{ display: inline-block; background: var(--c2); color: white; padding: 16px 36px; border-radius: 50px; font-weight: 700; text-decoration: none; font-size: 1rem; transition: background 0.2s; }}
        .cta-box a:hover {{ background: var(--c1); }}

        .source-note {{ font-size: 0.85rem; color: var(--ink4); margin-top: 30px; line-height: 1.6; padding: 20px; background: #FFFFFF; border-radius: 12px; border: 1px dashed var(--line); }}

        footer {{ text-align: center; padding: 60px 0; border-top: 1px solid var(--line); color: var(--ink4); font-size: 0.9rem; }}
        footer a {{ color: var(--ink4); text-decoration: none; margin: 0 12px; }}
        footer a:hover {{ color: var(--ink); }}

        @media (max-width: 768px) {{
            .header-section h1 {{ font-size: 2rem; }}
            .event-card {{ flex-direction: column; }}
            .event-date {{ width: 100%; text-align: left; display: flex; align-items: baseline; gap: 8px; }}
            .temple-grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="grain"></div>

    <nav>
        <div class="nav-bar">
            <a href="index.html" class="logo">
                <img src="/thaidata-lockup.b89c5cf2.png" alt="ThaiData UK" class="logo-icon" width="162" height="40">
            </a>
            <a href="guides.html" style="color:rgba(255,255,255,0.6); font-size:0.9rem; text-decoration:none;">&larr; Guides</a>
        </div>
    </nav>

    <div class="header-section">
        <div class="wrap">
            <div style="font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:0.1em; color:var(--c2); margin-bottom:16px;">2026 Events Calendar</div>
            <h1>Thai Festivals &<br>Events in the <em>UK</em></h1>
            <p>The only complete calendar of UK Thai cultural events. Songkran, Loy Krathong, food festivals, temple celebrations — every major event, every city, all in one place.</p>
        </div>
    </div>

    <!-- 2026 Calendar -->
    <div class="section">
        <div class="wrap">
            <h2><em>2026</em> Event Calendar</h2>
            <p style="color:var(--ink4); margin-bottom:20px;">Events are updated regularly. Dates marked * are estimated based on lunar calendar or previous years — confirm with the venue before travelling. Events that have already happened are marked Ended and kept for reference.</p>
{calendar_html}
        </div>
    </div>

    <!-- Temple Directory -->
    <div class="section">
        <div class="wrap">
            <h2>UK Thai <em>Temple Directory</em></h2>
            <p style="color:var(--ink4); margin-bottom:20px;">There are an estimated 35+ Thai Buddhist temples and meditation centres across the UK. Below are the major temples that host regular cultural events and festivals. Most welcome visitors — check opening times and dress modestly (covered shoulders and knees).</p>

            <div class="temple-grid">
                <div class="temple-card">
                    <div class="t-name">Wat Buddhapadipa<span class="thai">วัดพุทธปทีป</span></div>
                    <div class="t-loc"><i class="fas fa-map-marker-alt"></i>14 Calonne Road, Wimbledon, London SW19 5HJ</div>
                    <div class="t-events">🎉 The UK's first & largest Thai temple (est. 1965). Hosts UK's biggest Songkran and Loy Krathong. 60th anniversary in 2026. Open daily for visitors.</div>
                </div>
                <div class="temple-card">
                    <div class="t-name">Wat Phra Singh UK<span class="thai">วัดพระสิงห์</span></div>
                    <div class="t-loc"><i class="fas fa-map-marker-alt"></i>88 High Street, Runcorn, Cheshire WA7 1JH</div>
                    <div class="t-events">🎉 Major northern temple. Songkran, Loy Krathong, regular meditation. Building a new Ubosot Hall — one of only 3 in the UK.</div>
                </div>
                <div class="temple-card">
                    <div class="t-name">Wat Charoenbhavana (Manchester)<span class="thai">วัดเจริญภาวนา</span></div>
                    <div class="t-loc"><i class="fas fa-map-marker-alt"></i>Gardner House, Cheltenham Street, Salford M6 6WY</div>
                    <div class="t-events">🎉 First Thai temple in NW England. Dhammakaya tradition. Converted curtain-rail factory. Regular meditation and cultural events.</div>
                </div>
                <div class="temple-card">
                    <div class="t-name">Wat Mahathat UK<span class="thai">วัดมหาธาตุ</span></div>
                    <div class="t-loc"><i class="fas fa-map-marker-alt"></i>Eastfields House, Alrewas Road, Kings Bromley, DE13 7HR</div>
                    <div class="t-events">🎉 Near Birmingham. Led by Ajahn Laow (3x royal appointee). Songkran, Loy Krathong, Kathina. Peaceful countryside setting.</div>
                </div>
                <div class="temple-card">
                    <div class="t-name">WAT Buddharam Leeds<span class="thai">วัดพุทธาราม</span></div>
                    <div class="t-loc"><i class="fas fa-map-marker-alt"></i>Leeds LS6 2ET</div>
                    <div class="t-events">🎉 Serves the Yorkshire Thai community. Traditional ceremonies and cultural events.</div>
                </div>
                <div class="temple-card">
                    <div class="t-name">Wat Phra Dhammakaya London</div>
                    <div class="t-loc"><i class="fas fa-map-marker-alt"></i>Woking, Surrey</div>
                    <div class="t-events">🎉 Dhammakaya tradition. Modern facilities, frequent meditation retreats. Part of the global Dhammakaya network.</div>
                </div>
                <div class="temple-card">
                    <div class="t-name">Wat Sanghapadipa<span class="thai">วัดสังฆปทีป</span></div>
                    <div class="t-loc"><i class="fas fa-map-marker-alt"></i>Clase House, Pengwern Road, Swansea SA6 7LW</div>
                    <div class="t-events">🎉 Wales' only Thai temple. Songkran and cultural events for the Welsh Thai community.</div>
                </div>
                <div class="temple-card">
                    <div class="t-name">Wat Sangkhathan (Birmingham)</div>
                    <div class="t-loc"><i class="fas fa-map-marker-alt"></i>69 Coupers Road, Birmingham</div>
                    <div class="t-events">🎉 One of the earliest Thai temples in the Midlands. Regular cultural events.</div>
                </div>
                <div class="temple-card">
                    <div class="t-name">Wat Sriratanaram (Manchester)</div>
                    <div class="t-loc"><i class="fas fa-map-marker-alt"></i>Manchester</div>
                    <div class="t-events">🎉 Serves the northern Thai community. Traditional Lanna-style ceremonies and events.</div>
                </div>
                <div class="temple-card">
                    <div class="t-name">Wat Phra Dhammakaya Newcastle</div>
                    <div class="t-loc"><i class="fas fa-map-marker-alt"></i>Newcastle upon Tyne NE31</div>
                    <div class="t-events">🎉 North East England's Dhammakaya centre. Active on Facebook: dmcnewcastle.</div>
                </div>
                <div class="temple-card">
                    <div class="t-name">Wat Phra Dhammakaya Scotland</div>
                    <div class="t-loc"><i class="fas fa-map-marker-alt"></i>Helensburgh, Scotland</div>
                    <div class="t-events">🎉 Scotland's primary Thai Buddhist centre. Dhammakaya tradition. Support groups in Doncaster & Sheffield.</div>
                </div>
                <div class="temple-card">
                    <div class="t-name">Buddha Vihara Temple</div>
                    <div class="t-loc"><i class="fas fa-map-marker-alt"></i>Birmingham B6 6AN</div>
                    <div class="t-events">🎉 Buddhist temple serving Birmingham's diverse Buddhist community including Thai practitioners.</div>
                </div>
            </div>
            <div class="source-note" style="margin-top:20px;">
                <strong>Help us complete this directory:</strong> We estimate there are 35+ Thai Buddhist temples and meditation centres across the UK. Many have limited web presence (Facebook-only). If you know of a Thai temple not listed here — or spot incorrect information — please email <a href="mailto:hello@thaidata.uk" style="color:var(--c2);">hello@thaidata.uk</a>. We verify and update within 48 hours. All temples listed welcome respectful visitors — remove shoes before entering buildings, dress modestly (covered shoulders and knees), and maintain quiet during meditation.</div>
        </div>
    </div>

    <!-- CTA -->
    <div class="cta-box">
        <div class="wrap">
            <h2 style="font-family:'Archivo','Inter',system-ui,sans-serif; font-size:2rem; margin-bottom:12px;">Running a Thai restaurant?</h2>
            <p style="color:var(--ink4); margin-bottom:30px;">Festival dates are prime marketing opportunities. Plan your Songkran and Loy Krathong promotions with our free tools.</p>
            <a href="index.html"><i class="fas fa-calculator" style="margin-right:8px;"></i>Free Restaurant Tools</a>
        </div>
    </div>

    <footer>
        <div class="wrap">
            <p style="margin-bottom:10px;">
                <a href="index.html">Tools</a> · 
                <a href="how-many-thai-restaurants-uk.html">UK Thai Count</a> · 
                <a href="thai-restaurant-menu-pricing-uk.html">Menu Pricing</a> · 
                <a href="open-thai-restaurant-uk.html">Opening Guide</a> · 
                <a href="about.html">About</a>
            </p>
            <p>&copy; 2026 ThaiData UK. Event dates marked * are estimates — always confirm with the venue. We update this calendar regularly.</p>
        </div>
    </footer>
</body>
</html>'''


# ── Page: songkran-uk.html ──────────────────────────────────────────────

def gen_songkran_page(events):
    """Songkran guide page."""
    songkran_events = [e for e in events if e["festival_type"] == "songkran"
                       and e["event_id"] != "songkran-restaurant-promotions-2026"]
    # Build venue event cards
    venue_cards = ""
    for e in songkran_events:
        loc_addr = e["address"] or e["venue_name"]
        venue_cards += f'''            <div class="event-card">
                <div class="ev-city"><div class="city-name">{e["city"] or ""}</div><div class="city-venue">{e["venue_name"]}</div></div>
                <div class="ev-details">
                    <div class="ev-name">{e["event_name"]}</div>
                    <div class="ev-desc">{e["description"]}</div>
                </div>
            </div>
'''
    return f'''<!DOCTYPE html>
<html lang="en-GB">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Songkran 2026 UK — Thai New Year Events &amp; Dates | ThaiData</title>
    <meta name="description" content="Every UK Songkran celebration in 2026. Temple water ceremonies, food festivals, restaurant specials. London, Manchester, Birmingham, Swansea — find.">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="https://thaidata.uk/songkran-uk">

    <meta property="og:type" content="article">
    <meta property="og:url" content="https://thaidata.uk/songkran-uk">
    <meta property="og:title" content="Songkran (Thai New Year) UK 2026 — All Events & Where to Celebrate">
    <meta property="og:description" content="The complete guide to Songkran in the UK. Temple water ceremonies, food festivals, and restaurant specials across every region.">
    <meta property="og:image" content="https://thaidata.uk/thaidataukhero.webp">
    <meta property="og:locale" content="en_GB">

    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" media="print" onload="this.media='all'"><noscript><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" /></noscript>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet" media="print" onload="this.media='all'" /><noscript><link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet" /></noscript>
    <style>
        :root {{
            --c1: #A3132B; --c2: #A3132B; --dark: #FFFFFF; --ink: #1A1614; --ink2: #4A403C; --ink3: #7A6F6A; --ink4: #9C918C; --line: #E7DFD5; --bg: #FBF7F0; --gold: #F59E0B;
        }}
:focus-visible {{
            outline: 2px solid #10B981;
            outline-offset: 2px;
            border-radius: 4px;
        }}
        :focus:not(:focus-visible) {{
            outline: none;
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    img, svg, video, canvas {{
      max-width: 100%;
      height: auto
    }}
                html {{ overflow-x: hidden; }}
body {{ font-family: 'Inter', system-ui, sans-serif; color: var(--ink); background: var(--bg); line-height: 1.6; -webkit-font-smoothing: antialiased;;
      overflow-x: hidden
    }}
        .grain {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: url("/assets/noise.svg"); opacity: 0.03; pointer-events: none; z-index: 999; }}
        .wrap {{ max-width: 1100px; margin: 0 auto; padding: 0 20px; }}

        nav {{ background: var(--dark); border-bottom: 1px solid var(--line); height: 72px; display: flex; align-items: center; position: sticky; top: 0; z-index: 100; }}
        .nav-bar {{ max-width: 1100px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; padding: 0 20px; width: 100%; }}
        .logo {{ display: flex; align-items: center; gap: 14px; font-weight: 700; font-size: 1.5rem; color: var(--ink); text-decoration: none; }}
        .logo-icon {{ height: 40px; width: auto; display: inline-block; }}

        .header-section {{ padding: 80px 0 60px; text-align: center; position: relative; }}
        .header-section::before {{ content: ''; position: absolute; top: 50%; left: 50%; width: 600px; height: 600px; background: radial-gradient(circle, rgba(16,185,129,0.06) 0%, transparent 70%); transform: translate(-50%, -50%); pointer-events: none; }}
        .header-section h1 {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: clamp(2.5rem, 7vw, 3.8rem); font-weight: 800; line-height: 1.15; margin-bottom: 20px; position: relative; }}
        .header-section h1 em {{ font-style: normal; color: var(--c2); }}
        .header-section p {{ color: var(--ink4); font-size: 1.15rem; max-width: 650px; margin: 0 auto; position: relative; }}

        .section {{ padding: 30px 0 60px; }}
        .section h2 {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: 2rem; font-weight: 800; margin-bottom: 12px; }}
        .section h2 em {{ font-style: normal; color: var(--c2); }}
        .section p, .section li {{ color: var(--ink4); font-size: 0.95rem; line-height: 1.8; margin-bottom: 12px; }}

        .event-card {{ background: #FFFFFF; border: 1px solid var(--line); border-radius: 16px; padding: 24px 28px; margin: 14px 0; display: flex; gap: 20px; align-items: flex-start; transition: border-color 0.2s; }}
        .event-card:hover {{ border-color: var(--c2); }}
        .event-card .ev-city {{ flex-shrink: 0; width: 110px; }}
        .event-card .ev-city .city-name {{ font-weight: 700; color: var(--c2); font-size: 0.95rem; }}
        .event-card .ev-city .city-venue {{ color: var(--ink4); font-size: 0.78rem; margin-top: 2px; }}
        .event-card .ev-details {{ flex: 1; }}
        .event-card .ev-name {{ font-weight: 700; margin-bottom: 4px; }}
        .event-card .ev-desc {{ color: var(--ink4); font-size: 0.85rem; }}

        .insight-box {{ background: rgba(16,185,129,0.05); border: 1px solid rgba(16,185,129,0.2); border-radius: 14px; padding: 24px 28px; margin: 20px 0; }}
        .insight-box h3 {{ color: var(--c2); margin-bottom: 8px; font-size: 0.95rem; }}

        .cta-box {{ text-align: center; padding: 60px 0; }}
        .cta-box a {{ display: inline-block; background: var(--c2); color: white; padding: 16px 36px; border-radius: 50px; font-weight: 700; text-decoration: none; font-size: 1rem; transition: background 0.2s; }}
        .cta-box a:hover {{ background: var(--c1); }}

        .source-note {{ font-size: 0.85rem; color: var(--ink4); margin-top: 30px; line-height: 1.6; padding: 20px; background: #FFFFFF; border-radius: 12px; border: 1px dashed var(--line); }}

        footer {{ text-align: center; padding: 60px 0; border-top: 1px solid var(--line); color: var(--ink4); font-size: 0.9rem; }}
        footer a {{ color: var(--ink4); text-decoration: none; margin: 0 12px; }}
        footer a:hover {{ color: var(--ink); }}

        @media (max-width: 768px) {{
            .header-section h1 {{ font-size: 2rem; }}
            .event-card {{ flex-direction: column; }}
            .event-card .ev-city {{ width: 100%; }}
        }}
    </style>
<script type="application/ld+json">{{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{{"@type":"ListItem","position":1,"name":"Home","item":"https://thaidata.uk/"}},{{"@type":"ListItem","position":2,"name":"Guides","item":"https://thaidata.uk/guides"}},{{"@type":"ListItem","position":3,"name":"Songkran (Thai New Year) UK Events, Dates & Where to Celebrate"}}]}}</script>
</head>
<body>
    <div class="grain"></div>
    <nav>
        <div class="nav-bar">
            <a href="index.html" class="logo"><img src="/thaidata-lockup.b89c5cf2.png" alt="ThaiData UK" class="logo-icon" width="162" height="40"></a>
            <a href="thai-festivals-uk.html" style="color:rgba(255,255,255,0.6); font-size:0.9rem; text-decoration:none;">&larr; All Festivals</a>
        </div>
    </nav>

    <div class="header-section">
        <div class="wrap">
            <div style="font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:0.1em; color:var(--c2); margin-bottom:16px;">Next: 13–15 April 2027</div>
            <h1>Songkran <em>in the UK</em><br>Thai New Year 2026</h1>
            <p>Where to celebrate Songkran across the UK — temple water ceremonies, food festivals, restaurant specials, and what to expect at your first Thai New Year.</p>
        </div>
    </div>

    <div class="section" style="padding-top:0;">
        <div class="wrap">
            <h2>What is <em>Songkran?</em></h2>
            <p>Songkran (สงกรานต์) is the Thai New Year — the most important festival in Thai culture. Traditionally celebrated April 13–15, it marks the sun's transition into Aries and the end of the dry season. It's famous worldwide for its <strong style="color: var(--ink);">water fights</strong>, but in the UK, celebrations are more traditional: water pouring ceremonies over Buddha images and elders' hands (rod nam dum hua), merit-making at temples, sand pagoda building, and massive Thai food gatherings.</p>
            <p>In the UK, Songkran is the single biggest annual gathering of the Thai community — over 5,000 people attend Wat Buddhapadipa in Wimbledon alone. For restaurants, it's the peak marketing opportunity of the year.</p>

            <div class="insight-box">
                <h3>💡 For restaurant owners</h3>
                <p>Songkran is your biggest promotional window. Major chains (Rosa's Thai, Chaophraya, Thaikhun) run dedicated Songkran menus and events. If you're not planning your Songkran promotion by February, you're leaving money on the table. <a href="thai-restaurant-menu-pricing-uk.html" style="color:var(--c2);">Check our menu pricing guide</a> to plan a profitable Songkran special.</p>
            </div>
        </div>
    </div>

    <div class="section">
        <div class="wrap">
            <h2>Where to <em>Celebrate</em> in 2026</h2>
            <p>The 2026 celebrations have now ended. These temples hold Songkran every year — 2027 dates are typically confirmed from January. Check each temple's Facebook page for next year's dates.</p>
{venue_cards}
        </div>
    </div>

    <div class="section">
        <div class="wrap">
            <h2>Songkran <em>Traditions</em> You'll See</h2>
            <p><strong style="color: var(--ink);">Rod Nam Dum Hua (รดน้ำดำหัว)</strong> — The water pouring ceremony. Younger people pour scented water over the hands of elders and monks to ask for blessings. This is the spiritual heart of Songkran — not the water fights you see in Thailand tourism videos.</p>
            <p><strong style="color: var(--ink);">Sand Pagoda Building (ก่อเจดีย์ทราย)</strong> — Families build intricate sand pagodas at temple grounds, decorated with flowers and flags. It's believed to return the sand carried away on your shoes during the year. Wat Buddhapadipa's sand pagodas are particularly elaborate.</p>
            <p><strong style="color: var(--ink);">Making Merit (ทำบุญ)</strong> — Offering food to monks at dawn, releasing birds or fish, and donating to the temple. Most UK temples hold an early morning alms round — arrive by 7am if you want to participate.</p>
            <p><strong style="color: var(--ink);">Song Nam Phra (สรงน้ำพระ)</strong> — Pouring scented water over Buddha images. A purification ritual. Every UK temple sets up a Buddha statue for this purpose during Songkran.</p>
        </div>
    </div>

    <div class="section">
        <div class="wrap">
            <h2>Songkran at <em>Restaurants</em></h2>
            <p>Major Thai restaurant chains run Songkran promotions throughout April. These tend to be more commercial but are more accessible if you can't make it to a temple:</p>
            <ul>
                <li><strong>Rosa's Thai Cafe</strong> — 20+ UK locations. Typically runs a limited-edition Songkran menu with seasonal specials. Check their website from late March.</li>
                <li><strong>Chaophraya</strong> — Flagship restaurants in major cities. Hosts ticketed Songkran dinner events with set menus and cultural performances.</li>
                <li><strong>Thaikhun</strong> — Street-food style chain. Songkran specials and themed decor throughout April.</li>
                <li><strong>Giggling Squid</strong> — 50+ UK locations. Usually runs a Songkran set menu.</li>
                <li><strong>Independent Thai restaurants</strong> — Many run their own Songkran events. Check your local Thai restaurant's social media in late March.</li>
            </ul>
        </div>
    </div>

    <div class="cta-box">
        <div class="wrap">
            <h2 style="font-family:'Archivo','Inter',system-ui,sans-serif; font-size:2rem; margin-bottom:12px;">See the full 2026 calendar</h2>
            <p style="color:var(--ink4); margin-bottom:30px;">Songkran is just the start. Browse every Thai festival and event across the UK.</p>
            <a href="thai-festivals-uk.html"><i class="fas fa-calendar-alt" style="margin-right:8px;"></i>Full Festival Calendar</a>
        </div>
    </div>

    <footer>
        <div class="wrap">
            <p style="margin-bottom:10px;">
                <a href="index.html">Tools</a> · 
                <a href="thai-festivals-uk.html">Festivals</a> · 
                <a href="loy-krathong-uk.html">Loy Krathong</a> · 
                <a href="how-many-thai-restaurants-uk.html">UK Thai Count</a>
            </p>
            <p>&copy; 2026 ThaiData UK. Dates marked * are based on lunar calendar — confirm with venues before travelling.</p>
        </div>
    </footer>
</body>
</html>'''


# ── Page: loy-krathong-uk.html ──────────────────────────────────────────

def gen_loy_krathong_page(events):
    """Loy Krathong guide page."""
    lk_events = [e for e in events if e["festival_type"] == "loy_krathong"]
    venue_cards = ""
    # Map city display from event data
    city_map = {e["event_id"]: (e["city"] or "", e["venue_name"]) for e in lk_events}
    # Order: specific venues first, then university
    for e in sorted(lk_events, key=lambda x: (0 if x["organiser"] != "University Thai Societies" else 1)):
        city = e.get("city", "")
        if e["event_id"] == "loy-krathong-university-societies-2026":
            city_label = "National"
        else:
            city_label = city or ""
        venue_cards += f'''            <div class="event-card">
                <div class="ev-city"><div class="city-name">{city_label}</div><div class="city-venue">{e["venue_name"]}</div></div>
                <div class="ev-details">
                    <div class="ev-name">{e["event_name"]}</div>
                    <div class="ev-desc">{e["description"]}</div>
                </div>
            </div>
'''
    return f'''<!DOCTYPE html>
<html lang="en-GB">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Loy Krathong 2026 UK — Events, Dates &amp; Thai Food | ThaiData</title>
    <meta name="description" content="UK Loy Krathong celebrations in 2026. Float your krathong at temple lakes, enjoy lantern displays and Thai food. Events in London, Manchester, Birmingham.">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="https://thaidata.uk/loy-krathong-uk">

    <meta property="og:type" content="article">
    <meta property="og:url" content="https://thaidata.uk/loy-krathong-uk">
    <meta property="og:title" content="Loy Krathong UK 2026 — Festival of Lights Events & Where to Celebrate">
    <meta property="og:description" content="Every UK Loy Krathong event in 2026. Float your krathong at temple lakes, enjoy Thai food, lanterns, and one of the most beautiful Thai festivals.">
    <meta property="og:image" content="https://thaidata.uk/thaidataukhero.webp">
    <meta property="og:locale" content="en_GB">

    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" media="print" onload="this.media='all'"><noscript><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" /></noscript>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet" media="print" onload="this.media='all'" /><noscript><link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet" /></noscript>
    <style>
        :root {{
            --c1: #A3132B; --c2: #A3132B; --dark: #FFFFFF; --ink: #1A1614; --ink2: #4A403C; --ink3: #7A6F6A; --ink4: #9C918C; --line: #E7DFD5; --bg: #FBF7F0; --gold: #F59E0B;
        }}
:focus-visible {{
            outline: 2px solid #10B981;
            outline-offset: 2px;
            border-radius: 4px;
        }}
        :focus:not(:focus-visible) {{
            outline: none;
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    img, svg, video, canvas {{
      max-width: 100%;
      height: auto
    }}
                html {{ overflow-x: hidden; }}
body {{ font-family: 'Inter', system-ui, sans-serif; color: var(--ink); background: var(--bg); line-height: 1.6; -webkit-font-smoothing: antialiased;;
      overflow-x: hidden
    }}
        .grain {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: url("/assets/noise.svg"); opacity: 0.03; pointer-events: none; z-index: 999; }}
        .wrap {{ max-width: 1100px; margin: 0 auto; padding: 0 20px; }}

        nav {{ background: var(--dark); border-bottom: 1px solid var(--line); height: 72px; display: flex; align-items: center; position: sticky; top: 0; z-index: 100; }}
        .nav-bar {{ max-width: 1100px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; padding: 0 20px; width: 100%; }}
        .logo {{ display: flex; align-items: center; gap: 14px; font-weight: 700; font-size: 1.5rem; color: var(--ink); text-decoration: none; }}
        .logo-icon {{ height: 40px; width: auto; display: inline-block; }}

        .header-section {{ padding: 80px 0 60px; text-align: center; position: relative; }}
        .header-section::before {{ content: ''; position: absolute; top: 50%; left: 50%; width: 600px; height: 600px; background: radial-gradient(circle, rgba(245,158,11,0.06) 0%, transparent 70%); transform: translate(-50%, -50%); pointer-events: none; }}
        .header-section h1 {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: clamp(2.5rem, 7vw, 3.8rem); font-weight: 800; line-height: 1.15; margin-bottom: 20px; position: relative; }}
        .header-section h1 em {{ font-style: normal; color: var(--gold); }}
        .header-section p {{ color: var(--ink4); font-size: 1.15rem; max-width: 650px; margin: 0 auto; position: relative; }}

        .section {{ padding: 30px 0 60px; }}
        .section h2 {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: 2rem; font-weight: 800; margin-bottom: 12px; }}
        .section h2 em {{ font-style: normal; color: var(--gold); }}
        .section p, .section li {{ color: var(--ink4); font-size: 0.95rem; line-height: 1.8; margin-bottom: 12px; }}

        .event-card {{ background: #FFFFFF; border: 1px solid var(--line); border-radius: 16px; padding: 24px 28px; margin: 14px 0; display: flex; gap: 20px; align-items: flex-start; transition: border-color 0.2s; }}
        .event-card:hover {{ border-color: var(--gold); }}
        .event-card .ev-city {{ flex-shrink: 0; width: 110px; }}
        .event-card .ev-city .city-name {{ font-weight: 700; color: var(--gold); font-size: 0.95rem; }}
        .event-card .ev-city .city-venue {{ color: var(--ink4); font-size: 0.78rem; margin-top: 2px; }}
        .event-card .ev-details {{ flex: 1; }}
        .event-card .ev-name {{ font-weight: 700; margin-bottom: 4px; }}
        .event-card .ev-desc {{ color: var(--ink4); font-size: 0.85rem; }}

        .insight-box {{ background: rgba(245,158,11,0.05); border: 1px solid rgba(245,158,11,0.2); border-radius: 14px; padding: 24px 28px; margin: 20px 0; }}
        .insight-box h3 {{ color: var(--gold); margin-bottom: 8px; font-size: 0.95rem; }}

        .cta-box {{ text-align: center; padding: 60px 0; }}
        .cta-box a {{ display: inline-block; background: var(--c2); color: white; padding: 16px 36px; border-radius: 50px; font-weight: 700; text-decoration: none; font-size: 1rem; transition: background 0.2s; }}
        .cta-box a:hover {{ background: var(--c1); }}

        .source-note {{ font-size: 0.85rem; color: var(--ink4); margin-top: 30px; line-height: 1.6; padding: 20px; background: #FFFFFF; border-radius: 12px; border: 1px dashed var(--line); }}

        footer {{ text-align: center; padding: 60px 0; border-top: 1px solid var(--line); color: var(--ink4); font-size: 0.9rem; }}
        footer a {{ color: var(--ink4); text-decoration: none; margin: 0 12px; }}
        footer a:hover {{ color: var(--ink); }}

        @media (max-width: 768px) {{
            .header-section h1 {{ font-size: 2rem; }}
            .event-card {{ flex-direction: column; }}
            .event-card .ev-city {{ width: 100%; }}
        }}
    </style>
<script type="application/ld+json">{{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{{"@type":"ListItem","position":1,"name":"Home","item":"https://thaidata.uk/"}},{{"@type":"ListItem","position":2,"name":"Guides","item":"https://thaidata.uk/guides"}},{{"@type":"ListItem","position":3,"name":"Loy Krathong UK Festival of Lights Events & Where to Celebrate"}}]}}</script>
</head>
<body>
    <div class="grain"></div>
    <nav>
        <div class="nav-bar">
            <a href="index.html" class="logo"><img src="/thaidata-lockup.b89c5cf2.png" alt="ThaiData UK" class="logo-icon" width="162" height="40"></a>
            <a href="thai-festivals-uk.html" style="color:rgba(255,255,255,0.6); font-size:0.9rem; text-decoration:none;">&larr; All Festivals</a>
        </div>
    </nav>

    <div class="header-section">
        <div class="wrap">
            <div style="font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:0.1em; color:var(--gold); margin-bottom:16px;">November 2026 — Full Moon</div>
            <h1>Loy Krathong<br><em>in the UK</em></h1>
            <p>Thailand's festival of lights comes to Britain. Float your krathong on temple lakes, watch lantern displays, eat incredible Thai food — and experience the most beautiful night in the Thai calendar.</p>
        </div>
    </div>

    <div class="section" style="padding-top:0;">
        <div class="wrap">
            <h2>What is <em>Loy Krathong?</em></h2>
            <p>Loy Krathong (ลอยกระทง) is Thailand's festival of lights, celebrated on the full moon of the 12th lunar month — usually November. "Loy" means to float, and "krathong" is a small decorated basket made from banana leaves, flowers, candles, and incense. Millions of Thais float these krathongs on rivers, lakes, and ponds to pay respect to the water goddess (Phra Mae Khongkha), let go of misfortunes, and make wishes for the coming year.</p>
            <p>In the UK, Loy Krathong is celebrated at Thai temples — most notably at Wat Buddhapadipa in Wimbledon, which has its own lake. It's smaller than Songkran but arguably <strong style="color: var(--ink);">more beautiful</strong>. Candles floating on dark water, traditional Thai music, the smell of incense and street food — it's one of the UK's most photogenic cultural events.</p>

            <div class="insight-box">
                <h3>🔍 Why this page exists</h3>
                <p>We searched for "Loy Krathong UK" and found almost nothing useful — a few outdated Facebook events and one temple page. For one of Thailand's most famous festivals, UK coverage is nearly non-existent. If you've been looking for where to celebrate Loy Krathong in the UK, you now have your answer.</p>
            </div>
        </div>
    </div>

    <div class="section">
        <div class="wrap">
            <h2>Where to <em>Celebrate</em> in 2026</h2>
            <p>The full moon of the 12th Thai lunar month falls on <strong style="color: var(--ink);">Tuesday 24 November 2026</strong>, but UK temples set their own celebration dates — Wat Buddhapadipa holds its Loy Krathong on <strong style="color: var(--ink);">Saturday 14 November 2026</strong>, and Wat Mahathat combines it with Kathina on 1 November. Always use the venue's published date below.</p>
{venue_cards}
        </div>
    </div>

    <div class="section">
        <div class="wrap">
            <h2>How to <em>Make a Krathong</em></h2>
            <p>Most UK temples sell pre-made krathongs (£5–10), but making your own is part of the tradition. Here's how:</p>
            <ol>
                <li><strong style="color: var(--ink);">Base:</strong> A slice of banana tree trunk (available at Thai grocers) or a biodegradable circular base. Do NOT use polystyrene — it harms wildlife and is banned at most temples.</li>
                <li><strong style="color: var(--ink);">Leaves:</strong> Wrap banana leaves around the base, folded and pinned with small wooden sticks or toothpicks. No metal pins — they rust and pollute the water.</li>
                <li><strong style="color: var(--ink);">Flowers:</strong> Orchids, marigolds, lotus, or any bright flower. Arrange them in layers on top of the leaves.</li>
                <li><strong style="color: var(--ink);">Candle & incense:</strong> Three incense sticks and one small candle in the centre. These are lit just before floating.</li>
                <li><strong style="color: var(--ink);">Personal touches:</strong> Some people add a coin (for prosperity), a strand of hair (to float away troubles), or a small written wish tucked under the flowers.</li>
            </ol>
            <p>When you float it, make a wish. Tradition says if the candle stays lit until your krathong floats out of sight, your wish will come true.</p>
        </div>
    </div>

    <div class="section">
        <div class="wrap">
            <h2>Loy Krathong vs <em>Yi Peng</em></h2>
            <p>Many people confuse Loy Krathong with Yi Peng — the sky lantern festival in Chiang Mai. They happen around the same time but are different festivals:</p>
            <ul>
                <li><strong style="color: var(--ink);">Loy Krathong</strong> = floating krathongs on water. Celebrated across Thailand and at UK temples.</li>
                <li><strong style="color: var(--ink);">Yi Peng</strong> = releasing paper sky lanterns. Specific to northern Thailand (Lanna culture). Rarely celebrated in the UK due to fire safety regulations — most UK temples do not allow sky lanterns.</li>
            </ul>
            <p>In the UK, what you'll experience at temples is traditional Loy Krathong — water floating only. The photos you see online of thousands of lanterns in the sky are from Thailand.</p>
        </div>
    </div>

    <div class="section">
        <div class="wrap">
            <h2>Visitor <em>Tips</em></h2>
            <ul>
                <li><strong style="color: var(--ink);">Dress warmly</strong> — it's a November evening in the UK. The temple grounds get cold. Layers and a coat.</li>
                <li><strong style="color: var(--ink);">Bring cash</strong> — most temple food stalls and krathong sellers are cash-only. ATMs near Wimbledon are a 15-minute walk.</li>
                <li><strong style="color: var(--ink);">Arrive early</strong> — the best krathongs sell out. The sunset-to-darkness transition is the magic hour for photos.</li>
                <li><strong style="color: var(--ink);">Dress modestly</strong> — temples require covered shoulders and knees. This applies even during outdoor events.</li>
                <li><strong style="color: var(--ink);">Take photos, then put the phone away</strong> — the candles on water are genuinely beautiful. Get your shot, then just watch.</li>
                <li><strong style="color: var(--ink);">Bring a torch</strong> — temple grounds are dimly lit for atmosphere. You'll need light to navigate paths and read food stall menus.</li>
            </ul>
        </div>
    </div>

    <div class="cta-box">
        <div class="wrap">
            <h2 style="font-family:'Archivo','Inter',system-ui,sans-serif; font-size:2rem; margin-bottom:12px;">More Thai events near you</h2>
            <p style="color:var(--ink4); margin-bottom:30px;">Loy Krathong, Songkran, food festivals — every Thai event in the UK, one calendar.</p>
            <a href="thai-festivals-uk.html"><i class="fas fa-calendar-alt" style="margin-right:8px;"></i>Full Festival Calendar</a>
        </div>
    </div>

    <footer>
        <div class="wrap">
            <p style="margin-bottom:10px;">
                <a href="index.html">Tools</a> · 
                <a href="thai-festivals-uk.html">Festivals</a> · 
                <a href="songkran-uk.html">Songkran</a> · 
                <a href="how-many-thai-restaurants-uk.html">UK Thai Count</a>
            </p>
            <p>&copy; 2026 ThaiData UK. Loy Krathong date is estimated from the lunar calendar. Confirm with venues before travelling.</p>
        </div>
    </footer>
</body>
</html>'''


# ── Main ────────────────────────────────────────────────────────────────

def main():
    events = load_events()
    (REPO / "thai-festivals-uk.html").write_text(site_icons.transform(gen_calendar_page(events)))
    (REPO / "songkran-uk.html").write_text(site_icons.transform(gen_songkran_page(events)))
    (REPO / "loy-krathong-uk.html").write_text(site_icons.transform(gen_loy_krathong_page(events)))
    print("Generated 3 festival pages OK.")


if __name__ == "__main__":
    main()
