# ThaiData UK — Restaurant Data & Claim System

**https://thaidata.uk** — Business intelligence and interactive tools for UK Thai restaurant operators. Free, no signup.

## What's Here

- **8 Interactive Tools**: Minimum wage calculator, delivery profit calculator, hygiene lookup, staffing calculator, market reports, supplier price tracker, restaurant valuation, competitor radar
- **8 Content Guides**: Opening a restaurant, chef visas, marketing, revenue benchmarks, menu pricing, opening timeline, UK overview, city breakdown
- **15 City Pages**: Individual market data for major UK cities
- **API v1**: Free cities.json endpoint — no auth, no rate limit
- **Claim System**: Restaurant owners can claim and enhance their listings (new!)

## Claim Your Listing System (NEW)

Restaurant owners can now claim their listing and add enhanced data: description, photos, website, social media, opening hours, features, and more.

### Architecture

```
users ──→ /claim/           (search & submit claim)
           │
           ▼ POST /api/claim
           │
     [D1 Database]
     ├── claims table       (pending → approved/rejected)
     ├── listings table     (enhanced data)
     └── auth_tokens table  (magic links for owners)

admin ──→ /admin/           (review & approve claims)
           │
           ▼ PUT /api/admin  (approve/reject)

owner ──→ /listing/manage   (edit with magic link token)
           │
           ▼ PUT /api/listing
```

### Files

| File | Purpose |
|------|---------|
| `schema.sql` | D1 database schema — run once to initialize |
| `wrangler.toml` | Cloudflare Pages Functions config |
| `functions/_middleware.js` | CORS handler |
| `functions/api/claim.js` | POST submit claim, GET check status |
| `functions/api/admin.js` | POST login, GET list claims, PUT approve/reject |
| `functions/api/listing.js` | GET listing, PUT update, POST request magic link |
| `functions/api/search.js` | GET proxy FSA API search (filtered to Thai) |
| `claim/index.html` | Public claim page |
| `admin/index.html` | Admin panel (password protected) |
| `listing/manage.html` | Owner listing management |

### Setup Instructions

#### 1. Create D1 Database

In Cloudflare Dashboard:
```
Workers & Pages → D1 → Create Database
Name: thaidata-db
```

After creation, get the database ID and update `wrangler.toml`:
```toml
[[d1_databases]]
binding = "DB"
database_name = "thaidata-db"
database_id = "YOUR_DATABASE_ID_HERE"
```

#### 2. Create the Tables

```bash
wrangler d1 execute thaidata-db --file=schema.sql
```

#### 3. Set Environment Variables

In Cloudflare Dashboard:
```
Workers & Pages → thaidata-uk → Settings → Variables
```

Add:
- `ADMIN_PASSWORD` — your secure password for the admin panel
- `MAGIC_LINK_SECRET` — random 64-character string

#### 4. Deploy

Push to `main` — Cloudflare Pages auto-deploys:
```bash
git add -A && git commit -m "Add claim system" && git push origin main
```

The `functions/` directory is automatically picked up by Cloudflare Pages and deployed as Functions.

#### 5. Bind D1 to Pages

In Cloudflare Dashboard:
```
Workers & Pages → thaidata-uk → Settings → Functions → D1 database bindings
```
Bind `thaidata-db` with variable name `DB`.

### How Claims Work

1. **Owner visits** `/claim/`, searches for their restaurant
2. **Submits claim** with name, email, phone, and verification notes
3. **Admin reviews** at `/admin/` (password protected)
4. **On approval**: listing is created, owner receives magic link (via email or displayed in response)
5. **Owner edits** at `/listing/manage?token=...` — adds description, photos, hours, etc.
6. **Enhanced listing** appears on city pages (auto-loaded via `/api/listing?city=X`)

### Security Notes

- Magic link tokens are single-use and expire after 1 hour
- Admin sessions last 24 hours
- All API endpoints validate authentication
- Token hashing should be added in production (current: direct UUID)

## Data Sources

- Food Standards Agency (FSA) — hygiene ratings and establishment data
- Food Hygiene Information Scheme (FHIS) — Scotland data
- Manual research for chain restaurant counts

## Cron Job

Weekly FSA data refresh runs via `scripts/refresh_fsa_data.sh`:
```bash
# Runs Monday 9:00 AM — pulls latest FSA/FHIS data, regenerates city counts, pushes to GitHub
```

## License

MIT — data is from FSA (Open Government Licence).
