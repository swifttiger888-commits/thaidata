#!/usr/bin/env python3
"""
Import google_enrichment.json into D1 via thaidata.uk API.
Chunks entries and POSTs to /api/enrichment.
Requires ADMIN_PASSWORD in /tmp/.thaidata_admin_password or env var.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENRICHMENT_FILE = REPO / "data" / "google_enrichment.json"
API_URL = "https://thaidata.uk/api/enrichment"
CHUNK_SIZE = 100  # rows per POST

def get_password():
    """Read admin password from file or env."""
    pw_file = Path("/tmp/.thaidata_admin_password")
    if pw_file.exists():
        return pw_file.read_text().strip()
    pw = os.environ.get("THAIDATA_ADMIN_PASSWORD")
    if pw:
        return pw
    print("ERROR: Admin password not found.")
    print("  Save it to /tmp/.thaidata_admin_password or set THAIDATA_ADMIN_PASSWORD")
    sys.exit(1)

def main():
    if not ENRICHMENT_FILE.exists():
        print(f"ERROR: {ENRICHMENT_FILE} not found. Run enrich_google_places.py first.")
        sys.exit(1)

    with open(ENRICHMENT_FILE) as f:
        data = json.load(f)

    total = len(data)
    password = get_password()

    print(f"Importing {total} enrichment rows to D1...")
    print(f"Chunk size: {CHUNK_SIZE}, endpoint: {API_URL}")

    inserted = 0
    updated = 0
    errors = 0

    for i in range(0, total, CHUNK_SIZE):
        chunk = data[i:i + CHUNK_SIZE]
        chunk_num = i // CHUNK_SIZE + 1
        total_chunks = (total + CHUNK_SIZE - 1) // CHUNK_SIZE

        print(f"  Chunk {chunk_num}/{total_chunks} ({len(chunk)} rows)...", end=" ", flush=True)

        body = json.dumps({"entries": chunk}).encode()
        req = urllib.request.Request(
            API_URL,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {password}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read())
            if result.get("success"):
                inserted += result.get("inserted", 0)
                updated += result.get("updated", 0)
                chunk_errors = result.get("errors", [])
                if chunk_errors:
                    errors += len(chunk_errors)
                    print(f"⚠️  {len(chunk_errors)} errors")
                else:
                    print("✅")
            else:
                print(f"❌ {result}")
                errors += len(chunk)
        except urllib.error.HTTPError as e:
            body_text = e.read().decode()[:200]
            print(f"❌ HTTP {e.code}: {body_text}")
            errors += len(chunk)
        except Exception as e:
            print(f"❌ {e}")
            errors += len(chunk)

        time.sleep(0.2)

    print(f"\n{'='*50}")
    print(f"Import complete!")
    print(f"  ✅ Inserted: {inserted}")
    print(f"  🔄 Updated: {updated}")
    print(f"  ❌ Errors: {errors}")
    print(f"  📊 Total: {inserted + updated + errors}/{total}")

if __name__ == "__main__":
    main()
