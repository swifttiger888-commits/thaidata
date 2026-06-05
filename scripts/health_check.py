#!/usr/bin/env python3
"""
ThaiData UK — Health Check
===========================
Monitors site uptime and data freshness. Runs daily via cron.
Silent if all good (empty stdout → no notification).
Prints alert and exits 1 on any failure.

Checks:
  1. Uptime — HTTP HEAD to thaidata.uk returns 200
  2. Data freshness — restaurants.json updated < 8 days ago
"""

import json
import os
import sys
import urllib.request
from datetime import date

SITE_URL = "https://thaidata.uk"
DATA_FILE = "/tmp/thaidata-repo/data/restaurants.json"
MAX_DATA_AGE_DAYS = 8  # cron runs weekly, allow 1 day grace


def check_uptime() -> str | None:
    """Return error string if site is down, None if OK."""
    try:
        req = urllib.request.Request(SITE_URL, method="HEAD")
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status != 200:
                return f"Site returned HTTP {resp.status}"
        return None
    except Exception as e:
        return f"Site unreachable: {e}"


def check_data_freshness() -> str | None:
    """Return error string if data is stale, None if OK."""
    if not os.path.exists(DATA_FILE):
        return f"Data file not found: {DATA_FILE}"

    try:
        with open(DATA_FILE) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return f"Cannot read data file: {e}"

    updated = data.get("updated", "")
    if not updated:
        return "No 'updated' field in restaurants.json"

    try:
        parts = updated.split("-")
        updated_date = date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        return f"Invalid date format in 'updated': {updated}"

    age = (date.today() - updated_date).days
    if age > MAX_DATA_AGE_DAYS:
        return f"Data is {age} days old (last updated: {updated}, max {MAX_DATA_AGE_DAYS} days)"
    return None


def main() -> None:
    errors: list[str] = []

    uptime_err = check_uptime()
    if uptime_err:
        errors.append(uptime_err)

    freshness_err = check_data_freshness()
    if freshness_err:
        errors.append(freshness_err)

    if errors:
        print("🔴 ThaiData Health Check FAILED")
        print("=" * 35)
        for e in errors:
            print(f"  ❌ {e}")
        sys.exit(1)

    # Silent when healthy — cron with no_agent=True skips delivery on empty stdout
    sys.exit(0)


if __name__ == "__main__":
    main()
