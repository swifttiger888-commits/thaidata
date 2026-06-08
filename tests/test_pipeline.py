#!/usr/bin/env python3
"""
ThaiData UK — Pipeline Integration & Data Tests
================================================
Tests the data pipeline parsing, LA→city mapping, and data integrity.

Run: python3 -m pytest tests/  (or python3 -m unittest tests/test_pipeline.py)
"""

import json, os, sys, unittest, tempfile
from pathlib import Path
from typing import Any, Optional

REPO = Path(__file__).resolve().parent.parent

# Add scripts to path so we can import pipeline functions
sys.path.insert(0, str(REPO / 'scripts'))

from city_mapper import LA_TO_CITY, CITY_POPULATIONS, map_la_to_city, get_population
from fsa_client import count_by_la


def parse_fsa_establishment(e: dict) -> dict | None:
    """Match the logic from fetch_all_thai_data.py main()."""
    rating = e.get('RatingValue', '')
    if rating in ('Awaiting Inspection', 'AwaitingInspection', '', None):
        return None
    la_name = e.get('LocalAuthorityName', 'Unknown')
    city = map_la_to_city(la_name)
    addr_parts = []
    for i in range(1, 5):
        line = e.get(f'AddressLine{i}', '').strip()
        if line:
            addr_parts.append(line)
    btype = e.get('BusinessType', '')
    is_takeaway = 'Takeaway' in btype or 'takeaway' in btype.lower()
    return {
        'id': e['FHRSID'],
        'name': e.get('BusinessName', 'Unknown'),
        'type': 'takeaway' if is_takeaway else 'restaurant',
        'city': city,
        'local_authority': la_name,
        'postcode': e.get('PostCode', '').strip(),
        'address': ', '.join(addr_parts),
        'hygiene_rating': str(rating),
        'rating_date': e.get('RatingDate', ''),
        'longitude': e.get('Geocode', {}).get('Longitude', ''),
        'latitude': e.get('Geocode', {}).get('Latitude', ''),
    }


# ── Mock FSA responses ──────────────────────────────────────────────

MOCK_FSA_RECORD = {
    "FHRSID": 123456,
    "LocalAuthorityBusinessID": "12345",
    "BusinessName": "Test Thai Restaurant",
    "BusinessType": "Restaurant/Cafe/Canteen",
    "BusinessTypeId": 1,
    "AddressLine1": "123 High Street",
    "AddressLine2": "",
    "AddressLine3": "",
    "AddressLine4": "",
    "PostCode": "SW1A 1AA",
    "Phone": "",
    "RatingValue": "5",
    "RatingDate": "2025-06-15T00:00:00",
    "LocalAuthorityName": "Westminster",
    "LocalAuthorityWebSite": "",
    "LocalAuthorityEmailAddress": "",
    "SchemeType": "FHRS",
    "Geocode": {
        "Longitude": -0.1276,
        "Latitude": 51.5074,
    },
    "Scores": {
        "Hygiene": 5,
        "Structural": 5,
        "ConfidenceInManagement": 5,
    },
}


class TestLAToCityMapping(unittest.TestCase):
    """Test the Local Authority → city name mapping logic."""

    def test_london_boroughs(self) -> None:
        self.assertEqual(map_la_to_city('Westminster'), 'London')
        self.assertEqual(map_la_to_city('Camden'), 'London')
        self.assertEqual(map_la_to_city('Tower Hamlets'), 'London')
        self.assertEqual(map_la_to_city('City of London'), 'London')

    def test_direct_cities(self) -> None:
        self.assertEqual(map_la_to_city('Manchester'), 'Manchester')
        self.assertEqual(map_la_to_city('Birmingham'), 'Birmingham')
        self.assertEqual(map_la_to_city('Leeds'), 'Leeds')

    def test_suffixed_cities(self) -> None:
        self.assertEqual(map_la_to_city('Edinburgh (City of)'), 'Edinburgh')
        self.assertEqual(map_la_to_city('Glasgow City'), 'Glasgow')
        self.assertEqual(map_la_to_city('Dundee City'), 'Dundee')
        self.assertEqual(map_la_to_city('Aberdeen City'), 'Aberdeen')

    def test_hyphenated_cities(self) -> None:
        self.assertEqual(map_la_to_city('Brighton and Hove'), 'Brighton')
        self.assertEqual(map_la_to_city('Bournemouth, Christchurch and Poole'), 'Bournemouth')
        self.assertEqual(map_la_to_city('Kingston upon Hull'), 'Hull')
        self.assertEqual(map_la_to_city('Newcastle upon Tyne'), 'Newcastle')
        self.assertEqual(map_la_to_city('Blackburn with Darwen'), 'Blackburn')
        self.assertEqual(map_la_to_city('Southend-on-Sea'), 'Southend')
        self.assertEqual(map_la_to_city('Telford and Wrekin'), 'Telford')

    def test_unmapped_la_returns_self(self) -> None:
        """Unknown LAs should return the LA name as-is."""
        result = map_la_to_city('Some Obscure Council')
        self.assertEqual(result, 'Some Obscure Council')


class TestFsaParsing(unittest.TestCase):
    """Test FSA API response parsing."""

    def test_parse_valid_restaurant(self) -> None:
        result = parse_fsa_establishment(MOCK_FSA_RECORD)
        self.assertIsNotNone(result)
        self.assertEqual(result['id'], 123456)
        self.assertEqual(result['name'], 'Test Thai Restaurant')
        self.assertEqual(result['type'], 'restaurant')
        self.assertEqual(result['city'], 'London')
        self.assertEqual(result['hygiene_rating'], '5')
        self.assertEqual(result['postcode'], 'SW1A 1AA')
        self.assertEqual(result['address'], '123 High Street')

    def test_parse_takeaway(self) -> None:
        record = dict(MOCK_FSA_RECORD)
        record['BusinessType'] = 'Takeaway'
        result = parse_fsa_establishment(record)
        self.assertEqual(result['type'], 'takeaway')

    def test_skip_awaiting_inspection(self) -> None:
        record = dict(MOCK_FSA_RECORD)
        record['RatingValue'] = 'Awaiting Inspection'
        result = parse_fsa_establishment(record)
        self.assertIsNone(result)

    def test_skip_empty_rating(self) -> None:
        record = dict(MOCK_FSA_RECORD)
        record['RatingValue'] = ''
        result = parse_fsa_establishment(record)
        self.assertIsNone(result)

    def test_skip_none_rating(self) -> None:
        record = dict(MOCK_FSA_RECORD)
        record['RatingValue'] = None
        result = parse_fsa_establishment(record)
        self.assertIsNone(result)

    def test_geocode_missing(self) -> None:
        record = dict(MOCK_FSA_RECORD)
        record['Geocode'] = {}
        result = parse_fsa_establishment(record)
        self.assertEqual(result['longitude'], '')
        self.assertEqual(result['latitude'], '')

    def test_rating_non_numeric(self) -> None:
        record = dict(MOCK_FSA_RECORD)
        record['RatingValue'] = 'Exempt'
        result = parse_fsa_establishment(record)
        self.assertEqual(result['hygiene_rating'], 'Exempt')

    def test_missing_business_name(self) -> None:
        record = dict(MOCK_FSA_RECORD)
        del record['BusinessName']
        result = parse_fsa_establishment(record)
        self.assertEqual(result['name'], 'Unknown')

    def test_partial_address(self) -> None:
        record = dict(MOCK_FSA_RECORD)
        record['AddressLine2'] = 'Some Area'
        record['AddressLine3'] = 'A Town'
        result = parse_fsa_establishment(record)
        self.assertIn('Some Area', result['address'])


class TestDataIntegrity(unittest.TestCase):
    """Test the actual data files for consistency."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.restaurants_path = REPO / 'data' / 'restaurants.json'
        cls.cities_path = REPO / 'api' / 'v1' / 'cities.json'
        cls.data_path = REPO / 'api' / 'v1' / 'data.json'
        with open(cls.restaurants_path) as f:
            cls.restaurants = json.load(f)
        with open(cls.cities_path) as f:
            cls.cities = json.load(f)
        cls.data = {}
        if cls.data_path.exists():
            with open(cls.data_path) as f:
                cls.data = json.load(f)

    def test_metadata_total_matches_count(self) -> None:
        meta = self.restaurants.get('total', 0)
        actual = len(self.restaurants.get('restaurants', []))
        self.assertEqual(meta, actual,
                         f"metadata total={meta} != actual records={actual}")

    def test_city_total_matches_restaurant_total(self) -> None:
        meta_total = self.restaurants.get('total', 0)
        city_sum = sum(c['total_thai_businesses'] for c in self.cities['cities'])
        self.assertEqual(city_sum, meta_total,
                         f"cities sum={city_sum} != restaurants total={meta_total}")

    def test_no_duplicate_fhrsids(self) -> None:
        ids = [r['id'] for r in self.restaurants['restaurants']]
        dupes = [i for i in ids if ids.count(i) > 1]
        self.assertEqual(len(dupes), 0, f"Duplicate FHRSIDs: {sorted(set(dupes))}")

    def test_hygiene_ratings_valid(self) -> None:
        valid = {'0', '1', '2', '3', '4', '5', 'AwaitingPublication', 'Exempt', 'Pass', 'Improvement Required'}
        for r in self.restaurants['restaurants']:
            hr = r.get('hygiene_rating', '')
            self.assertIn(hr, valid, f"id={r['id']}: invalid hygiene_rating='{hr}'")

    def test_restaurant_type_split_consistent(self) -> None:
        city_rest = sum(c['restaurants'] for c in self.cities['cities'])
        city_take = sum(c['takeaways'] for c in self.cities['cities'])
        actual_rest = sum(1 for r in self.restaurants['restaurants'] if r.get('type') == 'restaurant')
        actual_take = sum(1 for r in self.restaurants['restaurants'] if r.get('type') == 'takeaway')
        self.assertEqual(city_rest, actual_rest)
        self.assertEqual(city_take, actual_take)

    def test_all_records_have_required_fields(self) -> None:
        required = ['id', 'name', 'type', 'city', 'local_authority', 'hygiene_rating']
        for r in self.restaurants['restaurants']:
            for field in required:
                self.assertIn(field, r, f"Missing field '{field}' in restaurant #{r.get('id', '?')}")
                self.assertNotEqual(r.get(field), '',
                                    f"Empty field '{field}' in restaurant #{r.get('id', '?')}")

    def test_cities_sorted_by_count_descending(self) -> None:
        counts = [c['total_thai_businesses'] for c in self.cities['cities']]
        self.assertEqual(counts, sorted(counts, reverse=True),
                         "Cities should be sorted by count descending")

    def test_avg_hygiene_rating_in_range(self) -> None:
        for c in self.cities['cities']:
            rating = c['avg_hygiene_rating']
            self.assertGreaterEqual(rating, 0)
            self.assertLessEqual(rating, 5)

    def test_restaurant_count_positive(self) -> None:
        for c in self.cities['cities']:
            self.assertGreater(c['total_thai_businesses'], 0,
                               f"City '{c['name']}' has 0 businesses")

    def test_data_json_consistency(self) -> None:
        if self.data:
            stat_total = self.data.get('statistics', {}).get('total_uk_thai_businesses', 0)
            self.assertEqual(stat_total, self.restaurants.get('total', 0))


# ═════════════════════════════════════════════════════════════════════
# NEW: city_mapper edge cases
# ═════════════════════════════════════════════════════════════════════

class TestCityMapperEdgeCases(unittest.TestCase):
    """Test edge cases for city_mapper functions (map_la_to_city, get_population)."""

    # ── map_la_to_city edge cases ────────────────────────────────────

    def test_empty_string(self) -> None:
        """map_la_to_city with empty string returns empty string."""
        self.assertEqual(map_la_to_city(''), '')

    def test_none_input(self) -> None:
        """map_la_to_city with None raises AttributeError (current behaviour)."""
        with self.assertRaises(AttributeError):
            map_la_to_city(None)

    # ── get_population edge cases ───────────────────────────────────

    def test_get_population_known_city(self) -> None:
        """get_population with known city returns correct population value."""
        self.assertEqual(get_population('London'), 8_970_000)
        self.assertEqual(get_population('Manchester'), 568_000)
        self.assertEqual(get_population('Edinburgh'), 548_000)
        self.assertEqual(get_population('Leeds'), 812_000)

    def test_get_population_unknown_city(self) -> None:
        """get_population with unknown city returns None."""
        self.assertIsNone(get_population('Narnia'))
        self.assertIsNone(get_population('Atlantis'))
        self.assertIsNone(get_population(''))

    def test_get_population_suffixed_city(self) -> None:
        """get_population strips common suffixes like ' City', ' District', etc."""
        self.assertEqual(get_population('Manchester City'), 568_000)
        self.assertEqual(get_population('Glasgow City'), 635_000)
        self.assertEqual(get_population('Dundee City'), 152_000)
        self.assertEqual(get_population('Aberdeen City'), 202_000)
        self.assertEqual(get_population('Leeds District'), 812_000)


# ═════════════════════════════════════════════════════════════════════
# NEW: FSA client (count_by_la) tests
# ═════════════════════════════════════════════════════════════════════

class TestFsaClient(unittest.TestCase):
    """Test the fsa_client.count_by_la function with various inputs."""

    def test_count_by_la_empty(self) -> None:
        """count_by_la with empty list returns empty dict."""
        self.assertEqual(count_by_la([]), {})

    def test_count_by_la_mixed_types(self) -> None:
        """count_by_la correctly separates restaurants and takeaways."""
        establishments = [
            {'LocalAuthorityName': 'Westminster', 'BusinessType': 'Restaurant/Cafe/Canteen', 'RatingValue': '5'},
            {'LocalAuthorityName': 'Westminster', 'BusinessType': 'Takeaway', 'RatingValue': '4'},
            {'LocalAuthorityName': 'Camden', 'BusinessType': 'Restaurant/Cafe/Canteen', 'RatingValue': '3'},
            {'LocalAuthorityName': 'Westminster', 'BusinessType': 'Restaurant/Cafe/Canteen', 'RatingValue': '4'},
        ]
        result = count_by_la(establishments)
        self.assertEqual(result, {
            'Westminster': {'total': 3, 'restaurants': 2, 'takeaways': 1},
            'Camden': {'total': 1, 'restaurants': 1, 'takeaways': 0},
        })

    def test_count_by_la_skips_awaiting_inspection(self) -> None:
        """count_by_la skips establishments awaiting inspection."""
        establishments = [
            {'LocalAuthorityName': 'Westminster', 'BusinessType': 'Restaurant/Cafe/Canteen', 'RatingValue': '5'},
            {'LocalAuthorityName': 'Westminster', 'BusinessType': 'Takeaway', 'RatingValue': 'Awaiting Inspection'},
            {'LocalAuthorityName': 'Camden', 'BusinessType': 'Restaurant/Cafe/Canteen', 'RatingValue': 'AwaitingInspection'},
        ]
        result = count_by_la(establishments)
        self.assertEqual(result, {
            'Westminster': {'total': 1, 'restaurants': 1, 'takeaways': 0},
        })

    def test_count_by_la_skips_empty_rating(self) -> None:
        """count_by_la skips establishments with empty or None rating."""
        establishments = [
            {'LocalAuthorityName': 'Westminster', 'BusinessType': 'Restaurant/Cafe/Canteen', 'RatingValue': '5'},
            {'LocalAuthorityName': 'Westminster', 'BusinessType': 'Takeaway', 'RatingValue': ''},
            {'LocalAuthorityName': 'Camden', 'BusinessType': 'Takeaway', 'RatingValue': None},
        ]
        result = count_by_la(establishments)
        self.assertEqual(result, {
            'Westminster': {'total': 1, 'restaurants': 1, 'takeaways': 0},
        })


# ═════════════════════════════════════════════════════════════════════
# NEW: Additional data integrity edge cases
# ═════════════════════════════════════════════════════════════════════

class TestDataIntegrityEdgeCases(unittest.TestCase):
    """Additional data integrity checks beyond the basic tests."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.restaurants_path = REPO / 'data' / 'restaurants.json'
        cls.cities_path = REPO / 'api' / 'v1' / 'cities.json'
        cls.data_path = REPO / 'api' / 'v1' / 'data.json'
        with open(cls.restaurants_path) as f:
            cls.restaurants = json.load(f)
        with open(cls.cities_path) as f:
            cls.cities = json.load(f)
        cls.data = {}
        if cls.data_path.exists():
            with open(cls.data_path) as f:
                cls.data = json.load(f)

    def test_rating_date_valid_iso_format(self) -> None:
        """Every restaurant with a rating_date should have valid ISO 8601 format."""
        import re
        iso_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$')
        for r in self.restaurants['restaurants']:
            rd = r.get('rating_date', '')
            if rd:  # only check non-empty dates
                self.assertTrue(
                    bool(iso_pattern.match(rd)),
                    f"id={r['id']}: rating_date '{rd}' is not valid ISO 8601"
                )

    def test_postcode_non_empty_80_percent(self) -> None:
        """At least 80% of restaurant records should have a non-empty postcode."""
        total = len(self.restaurants['restaurants'])
        empty_pc = sum(1 for r in self.restaurants['restaurants'] if not r.get('postcode', '').strip())
        non_empty_pct = (total - empty_pc) / total * 100
        self.assertGreaterEqual(
            non_empty_pct, 80.0,
            f"Only {non_empty_pct:.1f}% of records have non-empty postcodes "
            f"({total - empty_pc}/{total})"
        )

    def test_all_cities_appear_in_cities_json(self) -> None:
        """Every restaurant city value should exist in cities.json (no orphan values)."""
        known_cities = set(c['name'] for c in self.cities['cities'])
        restaurant_cities = set(r['city'] for r in self.restaurants['restaurants'])
        orphans = restaurant_cities - known_cities
        self.assertEqual(
            len(orphans), 0,
            f"Orphan city values not in cities.json: {sorted(orphans)}"
        )

    def test_per_100k_calculation_correct(self) -> None:
        """per_100k in cities.json should match (total / population * 100000) rounded to 1dp."""
        for city in self.cities['cities']:
            total = city['total_thai_businesses']
            pop = city['population']
            if pop is None or pop == 0:
                self.assertIsNone(city['per_100k'],
                                  f"City '{city['name']}': per_100k should be None when population is None/0")
                continue
            expected = round(total / pop * 100_000, 1)
            self.assertAlmostEqual(
                city['per_100k'], expected, places=1,
                msg=f"City '{city['name']}': per_100k={city['per_100k']}, expected≈{expected}"
            )

    def test_restaurant_name_not_empty(self) -> None:
        """Every restaurant record must have a non-empty name."""
        for r in self.restaurants['restaurants']:
            name = r.get('name', '')
            self.assertTrue(
                name and name.strip(),
                f"Restaurant id={r['id']} has empty name"
            )


# ═════════════════════════════════════════════════════════════════════
# NEW: Cross-file consistency tests
# ═════════════════════════════════════════════════════════════════════

class TestCrossFileConsistency(unittest.TestCase):
    """Verify consistency between city_mapper data structures."""

    def test_map_la_to_city_matches_la_to_city_keys(self) -> None:
        """For every key in LA_TO_CITY, map_la_to_city should return the mapped value."""
        for la, expected_city in LA_TO_CITY.items():
            with self.subTest(la=la):
                actual = map_la_to_city(la)
                self.assertEqual(
                    actual, expected_city,
                    f"map_la_to_city({la!r}) returned {actual!r}, expected {expected_city!r}"
                )

    def test_la_to_city_values_in_populations(self) -> None:
        """Every LA_TO_CITY value should have a corresponding entry in CITY_POPULATIONS
        (except known backward-compat aliases like 'Kirklees' which resolves via
        a separate LA→city mapping)."""
        # 'Kirklees' is a backward-compat LA name that maps to 'Huddersfield';
        # it appears as a value only because the reverse mapping 'Huddersfield' -> 'Kirklees'
        # exists.  It is not a population-tracked city.
        known_backward_compat = {'Kirklees'}
        for la, city in LA_TO_CITY.items():
            if city in known_backward_compat:
                continue
            with self.subTest(la=la, city=city):
                self.assertIsNotNone(
                    get_population(city),
                    f"City '{city}' (from LA '{la}') not found in CITY_POPULATIONS"
                )


if __name__ == '__main__':
    unittest.main()
