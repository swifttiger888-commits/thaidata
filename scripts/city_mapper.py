#!/usr/bin/env python3
"""
ThaiData UK — City mapping utilities.
Maps Local Authority names to parent cities and provides population data.
Shared by fetch_all_thai_data.py, refresh_fsa_data.py, and tests.
"""

from typing import Optional

# ── Local Authority → City mapping ───────────────────────────────────
# London boroughs → London, others mapped by common name
LA_TO_CITY: dict[str, str] = {
    # London boroughs
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
    # Named city corrections
    'Edinburgh (City of)': 'Edinburgh',
    'Glasgow City': 'Glasgow',
    'Manchester': 'Manchester',
    'Birmingham': 'Birmingham',
    'Leeds': 'Leeds',
    'Bristol': 'Bristol',
    'Liverpool': 'Liverpool',
    'Sheffield': 'Sheffield',
    'Newcastle upon Tyne': 'Newcastle',
    'Cardiff': 'Cardiff',
    'Belfast': 'Belfast',
    'Leicester': 'Leicester',
    'Bradford': 'Bradford',
    'Coventry': 'Coventry',
    'Nottingham': 'Nottingham',
    'Kingston upon Hull': 'Hull',
    'Plymouth': 'Plymouth',
    'Stoke-on-Trent': 'Stoke-on-Trent',
    'Wolverhampton': 'Wolverhampton',
    'Derby': 'Derby',
    'Southampton': 'Southampton',
    'Portsmouth': 'Portsmouth',
    'Brighton and Hove': 'Brighton',
    'Bournemouth, Christchurch and Poole': 'Bournemouth',
    'Swansea': 'Swansea',
    'Norwich': 'Norwich',
    'Oxford': 'Oxford',
    'Cambridge': 'Cambridge',
    'York': 'York',
    'Bath and North East Somerset': 'Bath',
    'Cheltenham': 'Cheltenham',
    'Sunderland': 'Sunderland',
    'Milton Keynes': 'Milton Keynes',
    'Luton': 'Luton',
    'Warrington': 'Warrington',
    'Slough': 'Slough',
    'Reading': 'Reading',
    'Blackpool': 'Blackpool',
    'Bolton': 'Bolton',
    'Stockport': 'Stockport',
    'Oldham': 'Oldham',
    'Wigan': 'Wigan',
    'Chelmsford': 'Chelmsford',
    'Huddersfield': 'Kirklees',  # Kirklees → Huddersfield (kept for backward compat)
    'Kirklees': 'Huddersfield',
    'Northampton': 'Northampton',
    'Swindon': 'Swindon',
    'Peterborough': 'Peterborough',
    'Dundee City': 'Dundee',
    'Aberdeen City': 'Aberdeen',
    'Inverness': 'Inverness',
    'Perth and Kinross': 'Perth',
    'Stirling': 'Stirling',
    'Exeter': 'Exeter',
    'Gloucester': 'Gloucester',
    'Worcester': 'Worcester',
    'Lincoln': 'Lincoln',
    'Canterbury': 'Canterbury',
    'Colchester': 'Colchester',
    'Ipswich': 'Ipswich',
    'Preston': 'Preston',
    'Blackburn with Darwen': 'Blackburn',
    'Southend-on-Sea': 'Southend',
    'Doncaster': 'Doncaster',
    'Wakefield': 'Wakefield',
    'Rotherham': 'Rotherham',
    'Telford and Wrekin': 'Telford',
    'Middlesbrough': 'Middlesbrough',
    'Darlington': 'Darlington',
    'Halton': 'Warrington',  # Halton includes Widnes/Runcorn
}

# ── Population data (ONS 2024 estimates, rounded) ────────────────────
CITY_POPULATIONS: dict[str, int] = {
    'London': 8970000, 'Birmingham': 1166000, 'Leeds': 812000,
    'Glasgow': 635000, 'Sheffield': 584000, 'Manchester': 568000,
    'Edinburgh': 548000, 'Liverpool': 500000, 'Bristol': 483000,
    'Bradford': 547000, 'Huddersfield': 437000, 'Leicester': 374000,
    'Coventry': 370000, 'Cardiff': 372000, 'Belfast': 345000,
    'Nottingham': 328000, 'Newcastle': 307000, 'Bolton': 300000,
    'Sunderland': 278000, 'Brighton': 277000, 'Hull': 266000,
    'Plymouth': 265000, 'Wolverhampton': 263000, 'Derby': 260000,
    'Southampton': 256000, 'Swansea': 247000, 'Oldham': 243000,
    'Milton Keynes': 292000, 'Stockport': 295000, 'Wigan': 333000,
    'Luton': 228000, 'York': 211000, 'Portsmouth': 208000,
    'Warrington': 212000, 'Slough': 164000, 'Bournemouth': 401000,
    'Norwich': 148000, 'Oxford': 164000, 'Cambridge': 146000,
    'Bath': 196000, 'Reading': 175000, 'Blackpool': 142000,
    'Northampton': 250000, 'Swindon': 236000, 'Peterborough': 218000,
    'Dundee': 152000, 'Aberdeen': 202000, 'Inverness': 71000,
    'Perth': 51000, 'Stirling': 49000, 'Exeter': 135000,
    'Cheltenham': 120000, 'Chelmsford': 184000, 'Gloucester': 132000,
    'Worcester': 105000, 'Lincoln': 104000, 'Canterbury': 64000,
    'Colchester': 195000, 'Ipswich': 150000, 'Preston': 150000,
    'Blackburn': 150000, 'Southend': 185000, 'Doncaster': 310000,
    'Wakefield': 345000, 'Rotherham': 265000, 'Telford': 160000,
    'Middlesbrough': 148000, 'Darlington': 108000, 'Stoke-on-Trent': 260000,
    'Salford': 260000, 'Wirral': 325000, 'Sefton': 275000,
    'Knowsley': 155000, 'St Helens': 185000, 'Rochdale': 227000,
    'Bury': 195000, 'Tameside': 230000, 'Trafford': 237000,
    'Cheshire East': 390000, 'Cheshire West and Chester': 357000,
    'Lancaster': 145000, 'East Riding of Yorkshire': 345000,
    'North Lincolnshire': 170000, 'North East Lincolnshire': 160000,
    'Shropshire': 325000, 'Staffordshire': 880000, 'Warwickshire': 590000,
    'West Northamptonshire': 430000, 'North Northamptonshire': 365000,
    'Bedford': 185000, 'Central Bedfordshire': 300000, 'Buckinghamshire': 560000,
    'Oxfordshire': 725000, 'West Berkshire': 162000, 'Wokingham': 180000,
    'Bracknell Forest': 128000, 'Windsor and Maidenhead': 158000,
    'Surrey': 1216000, 'Hertfordshire': 1200000, 'Essex': 1500000,
    'Kent': 1600000, 'Medway': 285000, 'East Sussex': 560000,
    'West Sussex': 890000, 'Hampshire': 1400000, 'Isle of Wight': 142000,
    'Dorset': 380000, 'Somerset': 580000, 'Devon': 820000,
    'Cornwall': 575000, 'Wiltshire': 520000, 'Gloucestershire': 650000,
    'Herefordshire': 195000, 'Worcestershire': 605000, 'Warrington': 212000,
}


def map_la_to_city(local_authority: str) -> str:
    """Map a Local Authority name to its parent city."""
    if local_authority in LA_TO_CITY:
        return LA_TO_CITY[local_authority]
    # Try stripping county suffixes
    for suffix in [' City', ' District', ' Borough', ' County', ' (B)', ' City Council']:
        if local_authority.endswith(suffix):
            stripped = local_authority[:-len(suffix)].strip()
            if stripped in CITY_POPULATIONS:
                return stripped
    # If LA contains a known city name, use that
    for city in sorted(CITY_POPULATIONS.keys(), key=len, reverse=True):
        if city.lower() in local_authority.lower():
            return city
    return local_authority


def get_population(city_name: str) -> Optional[int]:
    """Get population for a city, with fallbacks."""
    if city_name in CITY_POPULATIONS:
        return CITY_POPULATIONS[city_name]
    # Try removing county suffixes
    for suffix in [' City', ' District', ' Borough', ' County', ' (B)']:
        if city_name.endswith(suffix):
            stripped = city_name[:-len(suffix)].strip()
            if stripped in CITY_POPULATIONS:
                return CITY_POPULATIONS[stripped]
    return None
