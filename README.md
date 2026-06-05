# ThaiData UK — Restaurant Data & Claim System

**https://thaidata.uk** — Business intelligence and interactive tools for UK Thai restaurant operators. Free, no signup.

## What's Here

- **1,594 Restaurant Pages** — Auto-generated from FSA data, one per UK Thai restaurant
- **253 City Pages** — Market data per UK city with FSA hygiene ratings
- **28 Chain Profiles** — Detailed intelligence on Thai restaurant chains
- **8 Interactive Tools**: Wage calculator, delivery profit calculator, hygiene lookup, staffing calculator, market reports, supplier price tracker, restaurant valuation, competitor radar
- **8 Content Guides**: Opening a restaurant, chef visas, marketing, revenue benchmarks, menu pricing, opening timeline, UK overview, city breakdown
- **5 City Guides**: Enriched landing pages for Manchester, Leeds, Birmingham, Edinburgh, Bristol
- **35-Term Glossary**: Industry terms with cross-references
- **Free API v1**: Cities.json endpoint — no auth, no rate limit
- **MCP Server**: AI-callable tools at `/mcp` (JSON-RPC 2.0)
- **Claim System**: Restaurant owners can claim and enhance their listings

## Quick Start

```bash
# Clone
git clone https://github.com/swifttiger888-commits/thaidata.git
cd thaidata

# Python deps (stdlib only currently)
pip install -r requirements.txt  # or skip — no external deps needed

# Copy env template
cp .env.example .env
# Edit .env with your values

# Copy wrangler config
cp wrangler.toml.example wrangler.toml
# Edit wrangler.toml with your D1 database ID
```

## Architecture

```
                    ┌─────────────────────┐
                    │   FSA API (Gov UK)  │
                    └────────┬────────────┘
                             │ weekly cron (Mon 9am)
                             ▼
                    ┌─────────────────────┐
                    │ fetch_all_thai_data │──→ data/restaurants.json
                    │     .py (pipeline)  │──→ api/v1/cities.json
                    └────────┬────────────┘──→ api/v1/data.json
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
   generate_    generate_     generate_
   restaurant_   menu_price_  city_links_
   pages.py     page.py       .py
       │             │             │
       ▼             ▼             ▼
   r/[city]/    thai-menu-    cities/[city]
   [slug]/      price-index   .html
   index.html   .html
                              
   ┌──────────────────────────────────────────┐
   │     Cloudflare Pages (static deploy)     │
   │  git push → auto-build → thaidata.uk     │
   │                                          │
   │   functions/     ← API + MCP endpoints  │
   │     api/                                 │
   │       claim.js     POST /api/claim       │
   │       admin.js     POST/PUT /api/admin   │
   │       listing.js   GET/PUT /api/listing  │
   │       search.js    GET /api/search       │
   │       upload.js    POST /api/upload      │
   │       claimed.js   GET /api/claimed      │
   │       diag.js      GET /api/diag         │
   │     mcp.js         POST /mcp            │
   │     _middleware.js CORS                  │
   │                                          │
   │   D1 Database (SQLite)                   │
   │     claims, listings, auth_tokens        │
   └──────────────────────────────────────────┘
```

## Project Structure

```
thaidata/
├── scripts/
│   ├── fetch_all_thai_data.py     # Main data pipeline (FSA API → JSON)
│   ├── generate_restaurant_pages.py  # 1,594 individual restaurant pages
│   ├── generate_menu_price_page.py   # Menu price index page
│   ├── collect_menu_prices.py        # Manual price survey tool
│   ├── add_city_restaurant_links.py  # Link city pages → restaurant pages
│   └── websub-ping.py                # WebSub/IndexNow notification
├── functions/
│   ├── _middleware.js             # CORS handler
│   ├── mcp.js                     # MCP server (AI tools)
│   └── api/
│       ├── admin.js               # Admin panel API
│       ├── claim.js               # Claim submission
│       ├── claimed.js             # Claimed listing queries
│       ├── diag.js                # Diagnostics
│       ├── listing.js             # Listing management
│       ├── search.js              # FSA proxy search
│       └── upload.js              # Photo upload
├── data/
│   ├── restaurants.json           # 1,594 restaurants (SINGLE SOURCE OF TRUTH)
│   └── postcode_geocodes.json     # Geocoded postcodes
├── api/v1/
│   ├── cities.json                # 253 city statistics
│   └── data.json                  # Overview data
├── schema.sql                     # D1 database schema
├── wrangler.toml                  # Cloudflare Pages config (LIVE)
├── wrangler.toml.example          # Template for new devs
├── .env.example                   # Environment variable template
├── .gitignore
└── requirements.txt               # Python dependencies
```

## Data Pipeline

The weekly data refresh runs every **Monday at 9:00 AM** via cron job (Hermes Agent).

Pipeline steps:
1. `scripts/fetch_all_thai_data.py` — Fetches FSA FHRS + FHIS APIs
   - Searches by "Thai" keyword across all business types
   - Searches 11 named chains (Giggling Squid, Busaba, etc.) for non-"Thai" named restaurants
   - Deduplicates by FHRSID (first match wins)
   - Maps Local Authorities → cities via 85-entry lookup table
   - Computes city statistics (population density, avg hygiene rating)
   - Saves: `data/restaurants.json`, `api/v1/cities.json`, `api/v1/data.json`
2. `scripts/generate_restaurant_pages.py` — Generates individual /r/ pages
3. `scripts/add_city_restaurant_links.py` — Adds restaurant links to city pages
4. Push to git → Cloudflare Pages auto-deploys

Run manually:
```bash
python3 scripts/fetch_all_thai_data.py
python3 scripts/generate_restaurant_pages.py
python3 scripts/add_city_restaurant_links.py
git add -A && git commit -m "weekly data refresh" && git push origin main
```

**Note:** The pipeline script writes to `/tmp/thaidata-repo/` by default. Edit `REPO_DIR` at the top of `scripts/fetch_all_thai_data.py` if your working directory is different.

## Environment Variables

Set these in Cloudflare Dashboard (Workers & Pages → thaidata-uk → Settings → Variables):

| Variable | Required | Description |
|----------|----------|-------------|
| `ADMIN_PASSWORD` | Yes | Password for `/admin` panel |
| `MAGIC_LINK_SECRET` | Yes | 64+ char random key for claim token signing |
| `RESEND_API_KEY` | Yes | Resend.com API key (starts with `re_`) for magic link emails |
| `SITE_URL` | Yes | `https://thaidata.uk` |

## D1 Database Setup

```bash
# Create database
wrangler d1 create thaidata-db

# Update wrangler.toml with the returned database ID

# Initialize schema
wrangler d1 execute thaidata-db --file=schema.sql

# Bind in Cloudflare Dashboard:
# Workers & Pages → thaidata-uk → Settings → Functions → D1 database bindings
# Bind thaidata-db with variable name DB
```

## Deploy

```bash
# Push to main — Cloudflare Pages auto-deploys
git add -A && git commit -m "your message" && git push origin main
```

## Claim System Flow

1. Owner visits `/claim/`, searches for their restaurant
2. Submits claim with name, email, phone, verification notes
3. Admin reviews at `/admin/` (password protected)
4. On approval: listing created, owner receives magic link email via Resend
5. Owner edits at `/listing/manage?token=...` — description, photos, hours, etc.

Security:
- Magic link tokens: single-use, SHA-256 hashed, 1-hour expiry
- Admin sessions: 24-hour expiry
- Rate-limited admin login: 5 attempts / 15 min per IP

## Data Sources

- Food Standards Agency (FSA) — hygiene ratings and establishment data via FHRS API
- Food Hygiene Information Scheme (FHIS) — Scotland data
- Manual menu price surveys — 75 dish-price pairs across 5 cities
- ONS 2024 mid-year population estimates (for city per-capita calculations)

## License

MIT — data sourced from FSA (Open Government Licence).
