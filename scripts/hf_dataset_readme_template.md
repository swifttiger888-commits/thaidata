---
license: odbl
language: [en]
task_categories:
- text-retrieval
- tabular-classification
pretty_name: UK Thai Restaurant Database
size_categories:
- 1K<n<10K
viewer: true
tags:
- thailand
- restaurant
- food-safety
- united-kingdom
- hygiene-ratings
- business-intelligence
- hospitality
configs:
- config_name: restaurants
  data_files: restaurants.jsonl
- config_name: cities
  data_files: cities.jsonl
---

# UK Thai Restaurant Database 🇹🇭🇬🇧

**{{REST_COUNT}} Thai restaurants across {{CITY_COUNT}} UK cities and towns — with hygiene ratings, geolocation, and business classification.**

Sourced weekly from the [Food Standards Agency](https://www.food.gov.uk/) (FSA) official registers — the same data used by Google, Deliveroo, and UK local authorities.

## 🔗 Live Site
- [ThaiData UK](https://thaidata.uk) — free business intelligence tools for Thai restaurant operators
- [API](https://thaidata.uk/api/v1/data.json) — machine-readable JSON endpoint
- [MCP Server](https://thaidata.uk/mcp) — AI agents can query this data directly via Model Context Protocol

## 📊 Dataset Contents

### `restaurants` ({{REST_COUNT}} records)
| Field | Description |
|---|---|
| `id` | FSA FHRSID (unique identifier) |
| `name` | Registered business name |
| `type` | `restaurant` or `takeaway` |
| `city` | Mapped city/town name |
| `local_authority` | Original FSA Local Authority |
| `postcode` | UK postcode |
| `address` | Full address |
| `hygiene_rating` | 0–5 (FHRS) or Pass/Improvement Required (FHIS Scotland) |
| `rating_date` | Last inspection date |
| `latitude` / `longitude` | Geocoded coordinates (postcodes.io) |

### `cities` ({{CITY_COUNT}} records)
| Field | Description |
|---|---|
| `name` | City/town name |
| `population` | ONS 2024 mid-year estimate |
| `total_thai_businesses` | Total FSA-listed Thai businesses |
| `restaurants` | Dine-in restaurants |
| `takeaways` | Takeaway-only businesses |
| `per_100k` | Thai restaurants per 100,000 population |
| `avg_hygiene_rating` | Mean hygiene rating |
| `postcode_areas` | Number of postcode districts covered |

## 🏛️ Sources & Methodology

- **Restaurant counts & ratings:** [FSA FHRS](https://ratings.food.gov.uk/) + [FHIS](https://www.foodstandards.gov.scot/) (Scotland) — queried weekly via official API
- **Population data:** [ONS 2024 mid-year estimates](https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationestimates)
- **Geocoding:** [postcodes.io](https://postcodes.io/) (derived from Ordnance Survey OpenData)
- **Market size:** HMRC business counts + UKHospitality industry reports
- **Last updated:** {{LAST_UPDATED}} · Refreshed every Monday 9am UTC

## ⚠️ Known Limitations

- Some Thai restaurants operate under names not containing "Thai" — we search for 11 major chains by name, but independents with non-Thai names may be missed
- Scottish ratings use Pass/Improvement Required scheme (mapped to 3/1 for numeric comparison)
- City boundaries mapped from Local Authority areas — rural restaurants may be attributed to nearest major town
- ~{{UNGEOCODED_PCT}}% of postcodes could not be geocoded (very new or unusual postcodes)

## 📜 Citation

```
@misc{thaidata_uk_2026,
  title={UK Thai Restaurant Database},
  author={ThaiData UK},
  year={2026},
  url={https://thaidata.uk},
  note={Data sourced from Food Standards Agency FHRS/FHIS. Updated weekly.}
}
```

## 📄 License

This dataset is published under the [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/). You are free to share, create, and adapt this database as long as you attribute ThaiData UK and share-alike. The underlying FSA data is [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
