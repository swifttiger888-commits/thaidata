"""Guard: no stale national/city counts on live surfaces.

Single source of truth: data/restaurants.json. Pages presenting CURRENT data
must not carry old figures (1,263/1,268/1,265/1,557, 253/254 cities, London
275/411, Leeds 34, hygiene 56.7%). The two June-2026 snapshot pages
(state-of-uk-thai-food-2026.html and how-many-thai-restaurants-uk.html)
legitimately keep June numbers in their labelled tables and are excluded —
they carry a visible snapshot banner pointing at the live count (1,266).
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

STALE_TOKENS = [
    "1,263",
    "1,268",
    "1,265",
    "1,557",
    "253 cities",
    "253 UK cities",
    "254 UK cities",
    "254 cities",
    "254 areas",
    "London leads with 411",
    "London leads with 275",
    "Leeds (34)",
    "Manchester (28)",
    "1,000 dine-in",
    "241 takeaways",
    "1,241 restaurants and takeaways",
    "1,159 of",
    "26.4% of UK total",
    # Hygiene: 56.7% was a wrong-denominator June figure (all rows, incl.
    # unrated). Live rate is 62.3% of rated venues (Oct 2026).
    "56.7%",
    # Stale London references
    "London has 282",
    # Unsourced stats removed Oct 2026 (never re-introduce without a citation)
    "20.3%",
    "£2.1B",
    "4th fastest",
    "284+",
    # Phrase pass Oct 2026: the FSA "registers" nothing we hold — it lists businesses
    "FSA-registered",
    # Margin claims rewritten Oct 2026 to cited UK benchmarks
    "67-72%",
    "4–8% net profit",
]

SNAPSHOT_PAGES = {
    "state-of-uk-thai-food-2026.html",
    "how-many-thai-restaurants-uk.html",
}

# Generated listing pages (r/<city>/<slug>/) may contain digits that look
# similar (FSA ids, phones) but never the comma-formatted stale totals; they
# are skipped for speed and to avoid false positives. llms-full.txt mirrors
# the snapshot pages and legitimately contains their June figures.
SKIP_DIRS = {"r", "cities", "chains", "recipes", "learn", "tools", "admin", "analysis", "competitors", "th"}


def _live_files():
    for p in sorted(ROOT.rglob("*.html")):
        rel = p.relative_to(ROOT)
        if rel.parts[0] in SKIP_DIRS:
            continue
        if p.name in SNAPSHOT_PAGES:
            continue
        yield p
    yield ROOT / "llms.txt"


def test_no_stale_counts_on_live_surfaces():
    offenders = []
    for p in _live_files():
        txt = p.read_text(encoding="utf-8", errors="replace")
        for tok in STALE_TOKENS:
            if tok in txt:
                offenders.append(f"{p.relative_to(ROOT)}: {tok}")
    assert not offenders, "stale counts found:\n" + "\n".join(offenders)


def test_snapshot_pages_point_at_live_count():
    how_many = (ROOT / "how-many-thai-restaurants-uk.html").read_text(encoding="utf-8")
    report = (ROOT / "state-of-uk-thai-food-2026.html").read_text(encoding="utf-8")
    assert "June 2026 snapshot" in how_many
    assert "June 2026 snapshot" in report
    assert "1,266" in how_many and "1,266" in report
