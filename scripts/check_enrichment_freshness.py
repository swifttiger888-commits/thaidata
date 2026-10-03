#!/usr/bin/env python3
"""Fail the build if google_enrichment.json is older than 25 days.

Google Maps Platform ToS: Places API content must not be stored beyond the
allowed caching window (30 days). The build bakes this JSON into static HTML,
so shipping stale data breaches the retention rule. Refresh first with:
    python3 scripts/enrich_google_places.py
Exit 0 = fresh enough (or no enrichment file), exit 1 = stale — abort build.
"""
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENRICHMENT = REPO / "data" / "google_enrichment.json"
MAX_AGE_DAYS = 25

if not ENRICHMENT.exists():
    print("check_enrichment_freshness: no enrichment file — skipping (nothing baked)")
    sys.exit(0)

age_days = (time.time() - ENRICHMENT.stat().st_mtime) / 86400.0
if age_days > MAX_AGE_DAYS:
    print(
        f"check_enrichment_freshness: FAIL — google_enrichment.json is "
        f"{age_days:.0f} days old (limit {MAX_AGE_DAYS}). "
        f"Run scripts/enrich_google_places.py before building."
    )
    sys.exit(1)

print(f"check_enrichment_freshness: OK — enrichment {age_days:.0f} days old")
sys.exit(0)
