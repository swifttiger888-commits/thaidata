#!/usr/bin/env python3
"""
ThaiData UK — Health Check
===========================
Monitors site uptime, data freshness, and CI status.
Runs daily via GitHub Actions scheduled workflow.
Reports status to stdout and sends Telegram alert on failure.

Checks:
  1. Uptime — HTTP HEAD to thaidata.uk returns 200
  2. Data freshness — restaurants.json updated < 8 days ago
  3. CI status — last GitHub Actions run on main passed
"""

import json
import os
import sys
import urllib.request
from datetime import date

SITE_URL = "https://thaidata.uk"
DATA_FILE = "data/restaurants.json"
MAX_DATA_AGE_DAYS = 8
GITHUB_API = (
    "https://api.github.com/repos/swifttiger888-commits/thaidata"
    "/actions/runs?branch=main&per_page=1&status=completed"
)


def check_uptime() -> str | None:
    """Return error string if site is down, None if OK."""
    try:
        req = urllib.request.Request(
            SITE_URL,
            method="HEAD",
            headers={"User-Agent": "Mozilla/5.0 (compatible; ThaiDataHealth/1.0)"},
        )
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
        return (
            f"Data is {age} days old "
            f"(last updated: {updated}, max {MAX_DATA_AGE_DAYS} days)"
        )
    return None


def check_ci_status() -> str | None:
    """Return error string if last CI run failed, None if OK."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return "GITHUB_TOKEN not set — cannot check CI status"

    try:
        req = urllib.request.Request(
            GITHUB_API,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "ThaiDataHealth/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        runs = data.get("workflow_runs", [])
        if not runs:
            return "No completed CI runs found on main"

        last = runs[0]
        conclusion = last.get("conclusion")
        if conclusion != "success":
            run_number = last.get("run_number", "?")
            return (
                f"Last CI run (#{run_number}) concluded: {conclusion} "
                f"— {last.get('html_url', '')}"
            )
        return None

    except Exception as e:
        return f"CI status check failed: {e}"


def send_telegram_alert(errors: list[str]) -> None:
    """Send alert via Telegram Bot API if configured. Silent otherwise."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        return

    message = "🔴 ThaiData Health Check FAILED\n" + "\n".join(
        f"❌ {e}" for e in errors
    )
    payload = json.dumps(
        {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    ).encode()

    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"  ⚠️ Telegram notification failed: {e}")


def main() -> None:
    errors: list[str] = []

    print("=" * 40)
    print("  ThaiData UK — Daily Health Check")
    print(f"  {date.today().isoformat()}")
    print("=" * 40)

    # Check 1: Uptime
    uptime_err = check_uptime()
    if uptime_err:
        errors.append(uptime_err)
        print(f"  ❌ Uptime: FAILED — {uptime_err}")
    else:
        print(f"  ✅ Uptime: OK ({SITE_URL})")

    # Check 2: Data freshness
    freshness_err = check_data_freshness()
    if freshness_err:
        errors.append(freshness_err)
        print(f"  ❌ Data:  FAILED — {freshness_err}")
    else:
        print(f"  ✅ Data:  OK ({DATA_FILE})")

    # Check 3: CI status
    ci_err = check_ci_status()
    if ci_err:
        errors.append(ci_err)
        print(f"  ❌ CI:    FAILED — {ci_err}")
    else:
        print(f"  ✅ CI:    OK (last run passed)")

    # Report
    if errors:
        print(f"\n  ❌ {len(errors)} check(s) failed — alerts sent")
        send_telegram_alert(errors)
        sys.exit(1)

    print(f"\n  ✅ All checks passed")
    sys.exit(0)


if __name__ == "__main__":
    main()
