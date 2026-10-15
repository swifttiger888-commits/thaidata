"""Keep data/restaurants-search.json in lockstep with the live dataset.

The index powers homepage search, claim search, and /listing/manage. It was
previously a stale one-off build (June 2026) that hid takeaways and newer
venues from claim search - these tests stop that recurring.
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INDEX = REPO / 'data' / 'restaurants-search.json'


def _load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def test_index_exists_and_nonempty():
    idx = _load(INDEX)
    assert isinstance(idx, list) and len(idx) > 1200


def test_index_matches_dataset_ids():
    idx = _load(INDEX)
    data = _load(REPO / 'data' / 'restaurants.json')
    records = data['restaurants'] if isinstance(data, dict) else data
    idx_ids = {str(r['id']) for r in idx}
    data_ids = {str(r['id']) for r in records}
    assert idx_ids == data_ids, (
        f'index/dataset drift: {len(data_ids - idx_ids)} in data missing from '
        f'index, {len(idx_ids - data_ids)} in index not in data')


def test_no_excluded_ids_in_index():
    idx = _load(INDEX)
    excl = _load(REPO / 'data' / 'exclusions.json')
    excluded = {str(i) for i in excl.get('excluded_fsa_ids', [])}
    bad = excluded & {str(r['id']) for r in idx}
    assert not bad, f'excluded venues leaked into search index: {sorted(bad)}'


def test_required_fields_present():
    idx = _load(INDEX)
    for r in idx:
        assert r.get('id') and r.get('name'), r
        for key in ('city', 'pc', 'address', 'rating', 'business_type', 'listing_url'):
            assert key in r, f'missing {key} in {r.get("name")}'


def test_takeaway_venue_findable():
    # Khao Gaeng Thai (Leeds, takeaway, FHRSID 928931) exposed the claim-search
    # bug: the old FSA proxy filtered to businessTypeId=1 and could never see it.
    idx = _load(INDEX)
    hits = [r for r in idx if r['id'] == 928931]
    assert hits and hits[0]['name'] == 'Khao Gaeng Thai'


def test_listing_urls_point_to_site():
    idx = _load(INDEX)
    for r in idx[:200]:
        if r['listing_url']:
            assert r['listing_url'].startswith('https://thaidata.uk/'), r['listing_url']
