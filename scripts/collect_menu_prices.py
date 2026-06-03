#!/usr/bin/env python3
"""
ThaiData Menu Price Survey — Data Collection Script
====================================================
Collects dine-in and delivery prices for top 5 Thai dishes
across target UK cities. Run this when ready to gather data.

Output: /tmp/thai_menu_prices.json
Then use generate_menu_price_page.py to build the HTML page.

Data sources (in order of reliability):
  1. Restaurant websites (direct menu pages)
  2. Google Business Profile menu photos
  3. Deliveroo / Uber Eats / Just Eat listings
  4. TripAdvisor menu uploads

Methodology per restaurant:
  - Dine-in price: from website or GBP menu
  - Delivery price: from Deliveroo or Uber Eats listing
  - Commission estimate: (delivery - dine-in) / delivery * 100

Target: Top 5 dishes × 10 cities × 3 restaurants per city = 150 data points
"""

CITIES = [
    "London", "Manchester", "Leeds", "Birmingham", "Bristol",
    "Edinburgh", "Sheffield", "Brighton", "Liverpool", "Nottingham"
]

TOP_DISHES = [
    "Pad Thai (chicken/prawn)",
    "Green Curry (chicken)",
    "Tom Yum Soup (prawn)",
    "Massaman Curry (beef)",
    "Spring Rolls (vegetable, 4pc starter)"
]

# === MANUAL COLLECTION TEMPLATE ===
# Fill this in by browsing restaurant menus.
# Each city: pick 3 popular Thai restaurants from our FSA data.
# For each: find dine-in price AND delivery price for each dish.

SURVEY_TEMPLATE = {
    "collected": "YYYY-MM-DD",
    "methodology": "Manual collection from restaurant websites + delivery platforms",
    "notes": [
        "Dine-in prices from official websites or Google Business Profile menu photos",
        "Delivery prices from Deliveroo, Uber Eats, or Just Eat listings",
        "Prices exclude service charge and delivery fees",
        "Where a restaurant doesn't offer a dish, mark as null"
    ],
    "cities": {
        "London": {
            "restaurants": [
                {
                    "name": "Rosa's Thai Cafe (Soho)",
                    "fsa_id": "TBD",
                    "source_dine_in": "https://rosasthai.com/menu",
                    "source_delivery": "Deliveroo",
                    "delivery_platform": "Deliveroo",
                    "prices": {
                        "Pad Thai (chicken/prawn)": {"dine_in": None, "delivery": None},
                        "Green Curry (chicken)": {"dine_in": None, "delivery": None},
                        "Tom Yum Soup (prawn)": {"dine_in": None, "delivery": None},
                        "Massaman Curry (beef)": {"dine_in": None, "delivery": None},
                        "Spring Rolls (vegetable, 4pc starter)": {"dine_in": None, "delivery": None},
                    }
                },
                # Add 2 more restaurants per city...
            ]
        },
        # Add more cities...
    }
}

# === AUTOMATED COLLECTION HELPERS ===
# These are starting points — you'll need to manually verify prices.
# Web scraping restaurant menus is fragile; manual verification is essential.

def search_deliveroo_restaurants(city):
    """Search Deliveroo for Thai restaurants in a city. Returns slugs to check."""
    # Deliveroo search URL pattern:
    # https://deliveroo.co.uk/restaurants/{city}?cuisine=thai
    # This is a starting point — manual browsing is more reliable
    slug = city.lower().replace(' ', '-')
    url = f"https://deliveroo.co.uk/restaurants/{slug}?cuisine=thai"
    print(f"  Deliveroo search: {url}")
    return url

def search_ubereats_restaurants(city):
    """Search Uber Eats for Thai restaurants in a city."""
    slug = city.lower().replace(' ', '-')
    url = f"https://www.ubereats.com/gb/near/thai-restaurant/{slug}"
    print(f"  Uber Eats search: {url}")
    return url

def search_justeat_restaurants(city):
    """Search Just Eat for Thai restaurants in a city."""
    # Just Eat uses postcodes; city search is approximate
    print(f"  Just Eat: search 'Thai restaurant {city}' on just-eat.co.uk")
    return f"https://www.just-eat.co.uk/area/thai-{city.lower().replace(' ', '-')}"

# === QUICK-START: Print all search URLs for manual browsing ===
if __name__ == "__main__":
    print("=" * 60)
    print("THAIDATA MENU PRICE SURVEY — Quick-Start URLs")
    print("=" * 60)
    print("\nFor each city below, open the delivery links and find")
    print("Thai restaurants. Cross-reference with their websites")
    print("for dine-in prices. Fill in SURVEY_TEMPLATE above.\n")
    
    for city in CITIES:
        print(f"\n📍 {city.upper()}")
        search_deliveroo_restaurants(city)
        search_ubereats_restaurants(city)
        search_justeat_restaurants(city)
    
    print("\n" + "=" * 60)
    print("COLLECTION WORKFLOW:")
    print("=" * 60)
    print("""
1. For each city, open the 3 delivery links above
2. Find 3 popular Thai restaurants (use our FSA data for reference)
3. For each restaurant:
   a. Find their official website → note dine-in prices
   b. Find them on Deliveroo/Uber Eats → note delivery prices
   c. Record BOTH prices for each of the 5 target dishes
4. Fill in the SURVEY_TEMPLATE dict above
5. Save to /tmp/thai_menu_prices.json
6. Run generate_menu_price_page.py to build the HTML page

Expected time: ~2-3 hours for all 10 cities
Partial data (3-5 cities) still produces a useful page.
    """)
