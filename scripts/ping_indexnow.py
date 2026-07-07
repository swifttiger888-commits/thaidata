#!/usr/bin/env python3
"""
Ping IndexNow endpoints to notify search engines of content changes.
Called after every deploy.

Usage:
    python3 scripts/ping_indexnow.py                  # Ping homepage + sitemap
    python3 scripts/ping_indexnow.py --urls urls.txt  # Ping specific URLs

Environment:
    INDEXNOW_KEY  (optional, falls back to robots.txt key)
"""

import os, re, sys, urllib.request, urllib.parse, json

SITE = 'https://thaidata.uk'
REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))

# IndexNow endpoints
ENDPOINTS = [
    'https://www.bing.com/indexnow',
    'https://yandex.com/indexnow',
    'https://api.indexnow.org/indexnow',
]

def get_key():
    """Read IndexNow key from robots.txt or env."""
    key = os.environ.get('INDEXNOW_KEY')
    if key:
        return key
    # Fall back: parse from robots.txt
    robots_path = os.path.join(REPO, 'robots.txt')
    if os.path.exists(robots_path):
        with open(robots_path) as f:
            match = re.search(r'Key:\s*(\S+)', f.read())
            if match:
                return match.group(1)
    return None

def ping(key, urls):
    """Send IndexNow ping for a list of URLs to all supported endpoints."""
    payload = json.dumps({
        'host': 'thaidata.uk',
        'key': key,
        'keyLocation': f'{SITE}/{key}.txt',
        'urlList': urls,
    }).encode('utf-8')

    results = []
    for endpoint in ENDPOINTS:
        try:
            req = urllib.request.Request(endpoint, data=payload,
                headers={'Content-Type': 'application/json; charset=utf-8'})
            resp = urllib.request.urlopen(req, timeout=10)
            status = resp.getcode()
            results.append((endpoint, status, 'OK'))
        except urllib.error.HTTPError as e:
            results.append((endpoint, e.code, e.reason))
        except Exception as e:
            results.append((endpoint, 'ERR', str(e)))
    return results

def main():
    key = get_key()
    if not key:
        print("ERROR: No IndexNow key found. Set INDEXNOW_KEY env var or check robots.txt")
        sys.exit(1)

    # Determine URLs to ping
    if len(sys.argv) > 2 and sys.argv[1] == '--urls':
        path = sys.argv[2]
        with open(path) as f:
            urls = [line.strip() for line in f if line.strip()]
    else:
        # Default: homepage + sitemap
        urls = [
            SITE + '/',
            SITE + '/sitemap.xml',
        ]

    print(f"IndexNow key: {key[:8]}...{key[-4:]}")
    print(f"Pinging {len(urls)} URLs to {len(ENDPOINTS)} endpoints...")
    print()

    results = ping(key, urls)
    all_ok = True
    for endpoint, status, msg in results:
        short = endpoint.split('//')[1].split('/')[0]
        ok = status in (200, 202)
        if not ok:
            all_ok = False
        print(f"  {'✓' if ok else '✗'} {short:30s} → {status} ({msg})")

    print()
    if all_ok:
        print("All IndexNow pings successful.")
    else:
        print("Some IndexNow pings failed. Check above.")
        sys.exit(1)

if __name__ == '__main__':
    main()
