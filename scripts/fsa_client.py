#!/usr/bin/env python3
"""
ThaiData UK — FSA API client utilities.
Provides functions for fetching data from the Food Standards Agency API
and processing establishment data.
Shared by fetch_all_thai_data.py and refresh_fsa_data.py.
"""

import json
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from typing import Any


def fetch_all(name: str, business_type_id: str, scheme_key: str) -> list[dict[str, Any]]:
    """Fetch all establishments matching criteria from FSA API. Returns list of dicts."""
    all_ests: list[dict[str, Any]] = []
    page = 1
    page_size = 500
    encoded = urllib.parse.quote(name)
    while True:
        url = (f'https://api.ratings.food.gov.uk/Establishments'
               f'?name={encoded}&businessTypeId={business_type_id}'
               f'&schemeTypeKey={scheme_key}'
               f'&pageNumber={page}&pageSize={page_size}')
        try:
            req = urllib.request.Request(url, headers={
                'x-api-version': '2',
                'accept': 'application/json'
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
        except Exception as e:
            print(f"  ⚠️ Error: {e}")
            break
        ests = data.get('establishments', [])
        if not ests:
            break
        all_ests.extend(ests)
        if len(ests) < page_size:
            break
        page += 1
        time.sleep(0.15)
    return all_ests


def fetch_by_id(fhrisd: int) -> dict[str, Any] | None:
    """Fetch a single establishment by FHRSID.

    Used for curated allowlist IDs that keyword search coverage cannot
    reach (renames, names with no 'hai'/'thai' substring). Returns the
    establishment dict, or None when the FSA no longer holds it.
    """
    url = f'https://api.ratings.food.gov.uk/Establishments/{fhrisd}'
    try:
        req = urllib.request.Request(url, headers={
            'x-api-version': '2',
            'accept': 'application/json'
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        if not data.get('FHRSID'):
            return None
        return data
    except Exception as e:
        print(f"  ⚠️ fetch_by_id({fhrisd}) failed: {e}")
        return None


def count_by_la(establishments: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Group establishments by LocalAuthority, return counts."""
    by_la: dict[str, dict[str, int]] = defaultdict(lambda: {'total': 0, 'restaurants': 0, 'takeaways': 0})
    for e in establishments:
        la = e.get('LocalAuthorityName', 'Unknown')
        btype = e.get('BusinessType', '')
        rating = e.get('RatingValue', '')

        # Skip uninspected
        if rating in ('Awaiting Inspection', 'AwaitingInspection', '', None):
            continue

        by_la[la]['total'] += 1
        if 'Takeaway' in btype:
            by_la[la]['takeaways'] += 1
        else:
            by_la[la]['restaurants'] += 1
    return dict(by_la)
