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
    """Fetch all establishments matching criteria from FSA API. Returns list of dicts.

    Pagination is driven by the API's own meta.totalPages, and every page is
    retried with backoff before giving up. If a page still cannot be fetched,
    or the collected row count falls materially short of meta.totalCount, this
    raises — the pipeline must abort rather than silently publish a dataset
    with venues missing.
    """
    all_ests: list[dict[str, Any]] = []
    page = 1
    page_size = 500
    total_pages: int | None = None
    total_count: int | None = None
    max_attempts = 4
    encoded = urllib.parse.quote(name)

    while True:
        url = (f'https://api.ratings.food.gov.uk/Establishments'
               f'?name={encoded}&businessTypeId={business_type_id}'
               f'&schemeTypeKey={scheme_key}'
               f'&pageNumber={page}&pageSize={page_size}')

        data = None
        last_err: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                req = urllib.request.Request(url, headers={
                    'x-api-version': '2',
                    'accept': 'application/json'
                })
                with urllib.request.urlopen(req, timeout=30) as resp:
                    payload = json.loads(resp.read())
                rc = (payload.get('meta') or {}).get('returncode')
                if rc not in (None, 'OK'):
                    raise RuntimeError(f'FSA returncode {rc}')
                data = payload
                break
            except Exception as e:
                last_err = e
                if attempt < max_attempts:
                    time.sleep(2 ** (attempt - 1))  # 1s, 2s, 4s

        if data is None:
            raise RuntimeError(
                f'FSA page fetch failed after {max_attempts} attempts: {url} (last error: {last_err})'
            )

        meta = data.get('meta') or {}
        if meta.get('totalPages') is not None:
            total_pages = int(meta['totalPages'])
        if meta.get('totalCount') is not None:
            total_count = int(meta['totalCount'])

        ests = data.get('establishments') or []
        all_ests.extend(ests)

        if total_pages is not None:
            if not ests and page < total_pages:
                raise RuntimeError(
                    f'FSA page {page} of {total_pages} returned 0 rows — refusing to publish partial data'
                )
            if page >= total_pages:
                break
        else:
            # No pagination metadata: a short page means the last page.
            if len(ests) < page_size:
                break

        page += 1
        time.sleep(0.15)

    # Integrity check: allow a handful of rows to shift mid-fetch (a venue can be
    # delisted between page requests), but never a material shortfall.
    if total_count is not None and len(all_ests) < total_count:
        shortfall = total_count - len(all_ests)
        if shortfall > 5:
            raise RuntimeError(
                f'FSA pagination incomplete for {name!r}: collected {len(all_ests)} of {total_count} '
                f'({shortfall} missing)'
            )
        print(f"  ⚠️ {name!r}: collected {len(all_ests)} of {total_count} ({shortfall} short — tolerated drift)")

    # The API can shift rows between page requests; de-duplicate by FHRSID.
    seen: dict[int, dict[str, Any]] = {}
    for e in all_ests:
        fid = e.get('FHRSID')
        if fid is not None and fid not in seen:
            seen[fid] = e
    return list(seen.values()) if seen else all_ests


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
