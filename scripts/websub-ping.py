#!/usr/bin/env python3
"""WebSub ping — notifies pubsubhubbub hub that thaidata.uk content changed.
Run after each deploy that updates data (weekly FSA refresh, new pages, etc.)
"""

import urllib.request
import urllib.parse
import sys

HUB_URL = "https://pubsubhubbub.appspot.com/"

# URLs to ping — hub will re-fetch these and push to subscribers
PING_URLS = [
    "https://thaidata.uk/feed.json",
    "https://thaidata.uk/sitemap.xml",
    "https://thaidata.uk/how-many-thai-restaurants-uk",
    "https://thaidata.uk/state-of-uk-thai-food-2026",
    "https://thaidata.uk/thai-restaurants-city-breakdown-uk",
]

def ping_hub(feed_url):
    data = urllib.parse.urlencode({
        "hub.mode": "publish",
        "hub.url": feed_url,
    }).encode()
    
    req = urllib.request.Request(
        HUB_URL,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "ThaiDataUK-WebSub/1.0",
        }
    )
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            body = resp.read().decode()
            if status in (200, 204, 202):
                return True, f"OK ({status})"
            return False, f"HTTP {status}: {body[:100]}"
    except Exception as e:
        return False, str(e)

if __name__ == "__main__":
    print(f"WebSub ping → {HUB_URL}")
    ok = 0
    fail = 0
    for url in PING_URLS:
        success, msg = ping_hub(url)
        if success:
            ok += 1
            print(f"  ✓ {url}")
        else:
            fail += 1
            print(f"  ✗ {url} — {msg}")
    
    print(f"\n{ok} success, {fail} failed")
    sys.exit(0 if fail == 0 else 1)
