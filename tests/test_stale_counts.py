"""Guard: no stale national/city counts on live surfaces.

Single source of truth: data/restaurants.json. Pages presenting CURRENT data
must not carry the old June-2026 figures (1,268 / 1,265 / 1,557 / 253 cities).
The two June-2026 snapshot pages (state-of-uk-thai-food-2026.html and
how-many-thai-restaurants-uk.html) legitimately keep June numbers and are
excluded — they carry a visible snapshot banner pointing at the live count.
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

STALE_TOKENS = [
    "1,268",
    "1,265",
    "1,557",
    "253 cities",
    "London leads with 411",
    "Leeds (34)",
    "Manchester (28)",
    "26.4% of UK total",
    # Unsourced stats removed Oct 2026 (never re-introduce without a citation)
    "20.3%",
    "£2.1B",
    "4th fastest",
    "284+",
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
    assert "1,263" in how_many and "1,263" in report
