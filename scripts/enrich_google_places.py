#!/usr/bin/env python3
"""
Google Places enrichment for ThaiData restaurant pages.
Fetches Place ID + details for every restaurant in restaurants.json
and writes results to data/google_enrichment.json.
Uses Places API (New) — places.googleapis.com/v1/
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
OUTPUT = DATA / "google_enrichment.json"

# Read API key from file — durable path first; /tmp is wiped on reboot
key_file = Path(os.environ.get("GOOGLE_PLACES_KEY_FILE") or "/opt/thaidata-repo/secrets/google_places_key")
if not key_file.exists():
    key_file = Path("/tmp/.google_places_key")
if not key_file.exists():
    print("ERROR: Google Places API key not found.")
    print("  Save it to /opt/thaidata-repo/secrets/google_places_key (chmod 600),")
    print("  or set GOOGLE_PLACES_KEY_FILE, or fall back to /tmp/.google_places_key.")
    sys.exit(1)
API_KEY = key_file.read_text().strip()
PLACES_URL = "https://places.googleapis.com/v1/places"
FIND_PLACE_URL = f"{PLACES_URL}:searchText"
FIELD_MASK = (
    "id,displayName,editorialSummary,regularOpeningHours,"
    "rating,userRatingCount,priceLevel,"
    "nationalPhoneNumber,websiteUri,photos"
)

def api_call(method, url, body=None, field_mask=None):
    """Make a Places API call with retry on rate limit."""
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
    }
    if field_mask:
        headers["X-Goog-FieldMask"] = field_mask
    
    data = json.dumps(body).encode() if body else None
    
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body_text = e.read().decode()
            if e.code == 429:
                wait = 2 ** attempt
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            if e.code == 404:
                return None
            print(f"  HTTP {e.code}: {body_text[:200]}")
            return None
        except Exception as e:
            if attempt < 2:
                time.sleep(1)
                continue
            print(f"  Error: {e}")
            return None
    return None


def find_place(name, city, lat, lng):
    """Find Place by text search. Returns place_id or None."""
    query = f"{name} {city} UK"
    body = {"textQuery": query}
    
    # Add location bias if we have coordinates
    if lat and lng:
        body["locationBias"] = {
            "circle": {
                "center": {"latitude": float(lat), "longitude": float(lng)},
                "radius": 5000.0
            }
        }
    
    result = api_call("POST", FIND_PLACE_URL, body, field_mask="places.id")
    if result and result.get("places"):
        place = result["places"][0]
        return place["id"]
    return None


def get_place_details(place_id):
    """Get full Place Details. Returns dict or None."""
    url = f"{PLACES_URL}/{place_id}"
    return api_call("GET", url, field_mask=FIELD_MASK)


def map_price_level(level_str):
    """Map Google price level to display string."""
    mapping = {
        "PRICE_LEVEL_FREE": "Free",
        "PRICE_LEVEL_INEXPENSIVE": "£",
        "PRICE_LEVEL_MODERATE": "££",
        "PRICE_LEVEL_EXPENSIVE": "£££",
        "PRICE_LEVEL_VERY_EXPENSIVE": "££££",
    }
    return mapping.get(level_str, level_str)


def extract_photos(photos_array):
    """Extract compact photo references from Places API response."""
    if not photos_array:
        return []
    result = []
    for p in photos_array[:5]:  # max 5 photos
        result.append({
            "name": p.get("name", ""),
            "googleMapsUri": p.get("googleMapsUri", ""),
            "width": p.get("widthPx"),
            "height": p.get("heightPx"),
        })
    return result


def main():
    # Optional: --refresh-days N re-fetches entries whose fetched_at is older
    # than N days (Google ToS: Places content must not be retained >30 days).
    refresh_days = None
    if '--refresh-days' in sys.argv:
        try:
            refresh_days = int(sys.argv[sys.argv.index('--refresh-days') + 1])
        except (IndexError, ValueError):
            print("Usage: enrich_google_places.py [--refresh-days N]")
            sys.exit(2)

    def is_stale(entry):
        if refresh_days is None:
            return False
        fetched = entry.get('fetched_at')
        if not fetched:
            return True
        try:
            d = datetime.strptime(fetched, '%Y-%m-%d').date()
        except ValueError:
            return True
        return (date.today() - d).days > refresh_days

    # Load restaurants
    with open(DATA / "restaurants.json") as f:
        data = json.load(f)
    
    restaurants = data["restaurants"]
    total = len(restaurants)
    
    # Load existing enrichment if resuming
    existing = {}
    if OUTPUT.exists():
        with open(OUTPUT) as f:
            existing_data = json.load(f)
        for entry in existing_data:
            existing[entry["fsa_id"]] = entry
        print(f"Resuming: {len(existing)} already enriched, {total - len(existing)} remaining")
    
    results = []
    found = 0
    not_found = 0
    errors = 0
    skipped_existing = 0
    
    for i, r in enumerate(restaurants):
        fsa_id = r["id"]
        
        # Skip if already done (unless a --refresh-days re-fetch is due)
        if fsa_id in existing and not is_stale(existing[fsa_id]):
            results.append(existing[fsa_id])
            skipped_existing += 1
            continue
        
        name = r["name"]
        city = r["city"]
        lat = r.get("latitude")
        lng = r.get("longitude")
        
        print(f"[{i+1}/{total}] {name}, {city}...", end=" ", flush=True)
        
        # Step 1: Find Place
        place_id = find_place(name, city, lat, lng)
        if not place_id:
            print("❌ not found on Google Maps")
            not_found += 1
            # Still record as empty
            results.append({
                "fsa_id": fsa_id,
                "google_place_id": None,
                "rating": None,
                "review_count": None,
                "phone": None,
                "website": None,
                "opening_hours": None,
                "photos": None,
                "description": None,
                "price_level": None,
                "raw_response": None,
                "fetched_at": date.today().isoformat(),
            })
            continue
        details = get_place_details(place_id)
        if not details:
            print("❌ details fetch failed")
            errors += 1
            results.append({
                "fsa_id": fsa_id,
                "google_place_id": place_id,
                "rating": None,
                "review_count": None,
                "phone": None,
                "website": None,
                "opening_hours": None,
                "photos": None,
                "description": None,
                "price_level": None,
                "raw_response": None,
                "fetched_at": date.today().isoformat(),
            })
            continue
        # Extract fields
        desc = details.get("editorialSummary", {}).get("text", "")
        hours_data = details.get("regularOpeningHours")
        hours_json = json.dumps(hours_data.get("weekdayDescriptions", [])) if hours_data else None
        photos_json = json.dumps(extract_photos(details.get("photos", [])))
        price = map_price_level(details.get("priceLevel", ""))
        
        entry = {
            "fsa_id": fsa_id,
            "google_place_id": place_id,
            "rating": details.get("rating"),
            "review_count": details.get("userRatingCount"),
            "phone": details.get("nationalPhoneNumber"),
            "website": details.get("websiteUri"),
            "opening_hours": hours_json,
            "photos": photos_json,
            "description": desc,
            "price_level": price,
            "raw_response": json.dumps(details),
            "fetched_at": date.today().isoformat(),
        }
        results.append(entry)
        found += 1
        
        # Progress summary
        rating_str = f"⭐{details.get('rating', '?')}" if details.get('rating') else "no rating"
        print(f"✅ {place_id[:12]}... {rating_str}")
        
        # Rate limit: ~1 QPS for free tier safety
        time.sleep(0.35)
        
        # Save progress every 50 restaurants
        if (i + 1) % 50 == 0:
            with open(OUTPUT, "w") as f:
                json.dump(results, f, indent=2)
            print(f"  💾 Saved checkpoint at {i+1}/{total}")
    
    # Final save
    with open(OUTPUT, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n{'='*50}")
    print(f"Done! Total: {total}")
    print(f"  ✅ Enriched: {found}")
    print(f"  ❌ Not on Google Maps: {not_found}")
    print(f"  ⚠️  Errors: {errors}")
    print(f"  ⏭️  Skipped (existing): {skipped_existing}")
    print(f"  Output: {OUTPUT}")


if __name__ == "__main__":
    main()
