#!/usr/bin/env python3
"""
ThaiData UK — Pipeline Integration & Data Tests
================================================
Tests the data pipeline parsing, LA→city mapping, and data integrity.

Run: python3 -m pytest tests/  (or python3 -m unittest tests/test_pipeline.py)
"""

import json, os, sys, unittest, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Add scripts to path so we can import pipeline functions
sys.path.insert(0, str(REPO / 'scripts'))

# Import pipeline functions (they're top-level functions, not a module)
# We duplicate the critical ones here for testing, since the script
# is designed to be run, not imported.

# ── LA→City mapping (extracted from fetch_all_thai_data.py) ──────────

LA_TO_CITY = {
    'Westminster': 'London', 'Camden': 'London', 'Tower Hamlets': 'London',
    'Kensington and Chelsea': 'London', 'Hammersmith and Fulham': 'London',
    'Wandsworth': 'London', 'Islington': 'London', 'Lambeth': 'London',
    'Southwark': 'London', 'Hackney': 'London', 'Haringey': 'London',
    'Brent': 'London', 'Ealing': 'London', 'Barnet': 'London',
    'Hounslow': 'London', 'Newham': 'London', 'Croydon': 'London',
    'Bromley': 'London', 'Enfield': 'London', 'Lewisham': 'London',
    'Richmond upon Thames': 'London', 'Hillingdon': 'London',
    'Waltham Forest': 'London', 'Redbridge': 'London', 'Greenwich': 'London',
    'Merton': 'London', 'Harrow': 'London', 'Kingston upon Thames': 'London',
    'Bexley': 'London', 'Sutton': 'London', 'Barking and Dagenham': 'London',
    'Havering': 'London', 'City of London': 'London',
    'Edinburgh (City of)': 'Edinburgh',
    'Glasgow City': 'Glasgow',
    'Brighton and Hove': 'Brighton',
    'Bournemouth, Christchurch and Poole': 'Bournemouth',
    'Kingston upon Hull': 'Hull',
    'Newcastle upon Tyne': 'Newcastle',
    'Bath and North East Somerset': 'Bath',
    'Blackburn with Darwen': 'Blackburn',
    'Southend-on-Sea': 'Southend',
    'Telford and Wrekin': 'Telford',
    'Halton': 'Warrington',
    'Kirklees': 'Huddersfield',
    'Dundee City': 'Dundee',
    'Aberdeen City': 'Aberdeen',
    'Perth and Kinross': 'Perth',
    'Stoke-on-Trent': 'Stoke-on-Trent',
    'Wolverhampton': 'Wolverhampton',
    'Belfast': 'Belfast',
}

# Also include all non-London cities that pass through directly
DIRECT_CITIES = {
    'Manchester', 'Birmingham', 'Leeds', 'Bristol', 'Liverpool',
    'Sheffield', 'Cardiff', 'Leicester', 'Bradford', 'Coventry',
    'Nottingham', 'Plymouth', 'Derby', 'Southampton', 'Portsmouth',
    'Swansea', 'Norwich', 'Oxford', 'Cambridge', 'York',
    'Cheltenham', 'Chelmsford', 'Sunderland', 'Milton Keynes',
    'Luton', 'Warrington', 'Slough', 'Reading', 'Blackpool',
    'Bolton', 'Stockport', 'Oldham', 'Wigan', 'Northampton',
    'Swindon', 'Peterborough', 'Exeter', 'Gloucester', 'Worcester',
    'Lincoln', 'Canterbury', 'Colchester', 'Ipswich', 'Preston',
    'Blackburn', 'Doncaster', 'Wakefield', 'Rotherham', 'Telford',
    'Middlesbrough', 'Darlington', 'Inverness', 'Perth', 'Stirling',
    'Dundee', 'Aberdeen', 'Glasgow', 'Edinburgh',
}


def map_la_to_city(local_authority):
    """Match the exact logic from fetch_all_thai_data.py."""
    if local_authority in LA_TO_CITY:
        return LA_TO_CITY[local_authority]
    # Try direct match
    if local_authority in DIRECT_CITIES or local_authority in LA_TO_CITY.values():
        return local_authority
    # Try suffix stripping
    for suffix in [' City', ' District', ' Borough', ' County', ' (B)', ' City Council']:
        if local_authority.endswith(suffix):
            stripped = local_authority[:-len(suffix)].strip()
            if stripped in DIRECT_CITIES or stripped in LA_TO_CITY:
                return LA_TO_CITY.get(stripped, stripped)
    # Substring match
    for city in sorted(DIRECT_CITIES, key=len, reverse=True):
        if city.lower() in local_authority.lower():
            return city
    return local_authority


def parse_fsa_establishment(e):
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

    def test_london_boroughs(self):
        self.assertEqual(map_la_to_city('Westminster'), 'London')
        self.assertEqual(map_la_to_city('Camden'), 'London')
        self.assertEqual(map_la_to_city('Tower Hamlets'), 'London')
        self.assertEqual(map_la_to_city('City of London'), 'London')

    def test_direct_cities(self):
        self.assertEqual(map_la_to_city('Manchester'), 'Manchester')
        self.assertEqual(map_la_to_city('Birmingham'), 'Birmingham')
        self.assertEqual(map_la_to_city('Leeds'), 'Leeds')

    def test_suffixed_cities(self):
        self.assertEqual(map_la_to_city('Edinburgh (City of)'), 'Edinburgh')
        self.assertEqual(map_la_to_city('Glasgow City'), 'Glasgow')
        self.assertEqual(map_la_to_city('Dundee City'), 'Dundee')
        self.assertEqual(map_la_to_city('Aberdeen City'), 'Aberdeen')

    def test_hyphenated_cities(self):
        self.assertEqual(map_la_to_city('Brighton and Hove'), 'Brighton')
        self.assertEqual(map_la_to_city('Bournemouth, Christchurch and Poole'), 'Bournemouth')
        self.assertEqual(map_la_to_city('Kingston upon Hull'), 'Hull')
        self.assertEqual(map_la_to_city('Newcastle upon Tyne'), 'Newcastle')
        self.assertEqual(map_la_to_city('Blackburn with Darwen'), 'Blackburn')
        self.assertEqual(map_la_to_city('Southend-on-Sea'), 'Southend')
        self.assertEqual(map_la_to_city('Telford and Wrekin'), 'Telford')

    def test_unmapped_la_returns_self(self):
        """Unknown LAs should return the LA name as-is."""
        result = map_la_to_city('Some Obscure Council')
        self.assertEqual(result, 'Some Obscure Council')


class TestFsaParsing(unittest.TestCase):
    """Test FSA API response parsing."""

    def test_parse_valid_restaurant(self):
        result = parse_fsa_establishment(MOCK_FSA_RECORD)
        self.assertIsNotNone(result)
        self.assertEqual(result['id'], 123456)
        self.assertEqual(result['name'], 'Test Thai Restaurant')
        self.assertEqual(result['type'], 'restaurant')
        self.assertEqual(result['city'], 'London')
        self.assertEqual(result['hygiene_rating'], '5')
        self.assertEqual(result['postcode'], 'SW1A 1AA')
        self.assertEqual(result['address'], '123 High Street')

    def test_parse_takeaway(self):
        record = dict(MOCK_FSA_RECORD)
        record['BusinessType'] = 'Takeaway'
        result = parse_fsa_establishment(record)
        self.assertEqual(result['type'], 'takeaway')

    def test_skip_awaiting_inspection(self):
        record = dict(MOCK_FSA_RECORD)
        record['RatingValue'] = 'Awaiting Inspection'
        result = parse_fsa_establishment(record)
        self.assertIsNone(result)

    def test_skip_empty_rating(self):
        record = dict(MOCK_FSA_RECORD)
        record['RatingValue'] = ''
        result = parse_fsa_establishment(record)
        self.assertIsNone(result)

    def test_skip_none_rating(self):
        record = dict(MOCK_FSA_RECORD)
        record['RatingValue'] = None
        result = parse_fsa_establishment(record)
        self.assertIsNone(result)

    def test_geocode_missing(self):
        record = dict(MOCK_FSA_RECORD)
        record['Geocode'] = {}
        result = parse_fsa_establishment(record)
        self.assertEqual(result['longitude'], '')
        self.assertEqual(result['latitude'], '')

    def test_rating_non_numeric(self):
        record = dict(MOCK_FSA_RECORD)
        record['RatingValue'] = 'Exempt'
        result = parse_fsa_establishment(record)
        self.assertEqual(result['hygiene_rating'], 'Exempt')

    def test_missing_business_name(self):
        record = dict(MOCK_FSA_RECORD)
        del record['BusinessName']
        result = parse_fsa_establishment(record)
        self.assertEqual(result['name'], 'Unknown')

    def test_partial_address(self):
        record = dict(MOCK_FSA_RECORD)
        record['AddressLine2'] = 'Some Area'
        record['AddressLine3'] = 'A Town'
        result = parse_fsa_establishment(record)
        self.assertIn('Some Area', result['address'])


class TestDataIntegrity(unittest.TestCase):
    """Test the actual data files for consistency."""

    @classmethod
    def setUpClass(cls):
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

    def test_metadata_total_matches_count(self):
        meta = self.restaurants.get('total', 0)
        actual = len(self.restaurants.get('restaurants', []))
        self.assertEqual(meta, actual,
                         f"metadata total={meta} != actual records={actual}")

    def test_city_total_matches_restaurant_total(self):
        meta_total = self.restaurants.get('total', 0)
        city_sum = sum(c['total_thai_businesses'] for c in self.cities['cities'])
        self.assertEqual(city_sum, meta_total,
                         f"cities sum={city_sum} != restaurants total={meta_total}")

    def test_no_duplicate_fhrsids(self):
        ids = [r['id'] for r in self.restaurants['restaurants']]
        dupes = [i for i in ids if ids.count(i) > 1]
        self.assertEqual(len(dupes), 0, f"Duplicate FHRSIDs: {sorted(set(dupes))}")

    def test_hygiene_ratings_valid(self):
        valid = {'0', '1', '2', '3', '4', '5', 'AwaitingPublication', 'Exempt'}
        for r in self.restaurants['restaurants']:
            hr = r.get('hygiene_rating', '')
            self.assertIn(hr, valid, f"id={r['id']}: invalid hygiene_rating='{hr}'")

    def test_restaurant_type_split_consistent(self):
        city_rest = sum(c['restaurants'] for c in self.cities['cities'])
        city_take = sum(c['takeaways'] for c in self.cities['cities'])
        actual_rest = sum(1 for r in self.restaurants['restaurants'] if r.get('type') == 'restaurant')
        actual_take = sum(1 for r in self.restaurants['restaurants'] if r.get('type') == 'takeaway')
        self.assertEqual(city_rest, actual_rest)
        self.assertEqual(city_take, actual_take)

    def test_all_records_have_required_fields(self):
        required = ['id', 'name', 'type', 'city', 'local_authority', 'hygiene_rating']
        for r in self.restaurants['restaurants']:
            for field in required:
                self.assertIn(field, r, f"Missing field '{field}' in restaurant #{r.get('id', '?')}")
                self.assertNotEqual(r.get(field), '',
                                    f"Empty field '{field}' in restaurant #{r.get('id', '?')}")

    def test_cities_sorted_by_count_descending(self):
        counts = [c['total_thai_businesses'] for c in self.cities['cities']]
        self.assertEqual(counts, sorted(counts, reverse=True),
                         "Cities should be sorted by count descending")

    def test_avg_hygiene_rating_in_range(self):
        for c in self.cities['cities']:
            rating = c['avg_hygiene_rating']
            self.assertGreaterEqual(rating, 0)
            self.assertLessEqual(rating, 5)

    def test_restaurant_count_positive(self):
        for c in self.cities['cities']:
            self.assertGreater(c['total_thai_businesses'], 0,
                               f"City '{c['name']}' has 0 businesses")

    def test_data_json_consistency(self):
        if self.data:
            stat_total = self.data.get('statistics', {}).get('total_uk_thai_businesses', 0)
            self.assertEqual(stat_total, self.restaurants.get('total', 0))


if __name__ == '__main__':
    unittest.main()
