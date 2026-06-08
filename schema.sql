-- ThaiData UK — Claim Your Listing
-- D1 Database Schema
-- Run this in Cloudflare D1: wrangler d1 execute thaidata-db --file=schema.sql

-- Claims table: restaurant owners request ownership
CREATE TABLE IF NOT EXISTS claims (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  restaurant_name TEXT NOT NULL,
  city TEXT NOT NULL,
  fsa_id TEXT,
  business_type TEXT DEFAULT 'restaurant',
  claim_status TEXT DEFAULT 'pending',  -- pending | approved | rejected
  claimer_name TEXT NOT NULL,
  claimer_email TEXT NOT NULL,
  claimer_phone TEXT,
  claimer_role TEXT DEFAULT 'owner',
  verification_notes TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  reviewed_at TEXT,
  admin_notes TEXT
);

-- Listings table: enhanced data for claimed restaurants
CREATE TABLE IF NOT EXISTS listings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  claim_id INTEGER REFERENCES claims(id),
  restaurant_name TEXT NOT NULL,
  city TEXT NOT NULL,
  fsa_id TEXT,
  description TEXT,
  cuisine_specialty TEXT,
  website TEXT,
  phone TEXT,
  email TEXT,
  social_instagram TEXT,
  social_facebook TEXT,
  social_twitter TEXT,
  address TEXT,
  postcode TEXT,
  opening_hours TEXT,
  price_range TEXT,  -- £ | ££ | £££
  features TEXT,      -- JSON array string
  photos TEXT,        -- JSON array string of URLs
  menu_highlights TEXT, -- JSON array of {category, name, description, price}
  enrichment TEXT,     -- JSON: {scraped_at, source_url, status, fields[{value,found_in,confidence}]}
  claimed_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

-- Magic link tokens for owner authentication
CREATE TABLE IF NOT EXISTS auth_tokens (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  listing_id INTEGER REFERENCES listings(id),
  token_hash TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now')),
  expires_at TEXT NOT NULL,
  used INTEGER DEFAULT 0
);

-- Admin sessions (simple password-based, no email)
CREATE TABLE IF NOT EXISTS admin_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token TEXT NOT NULL UNIQUE,
  created_at TEXT DEFAULT (datetime('now')),
  expires_at TEXT NOT NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_claims_status ON claims(claim_status);
CREATE INDEX IF NOT EXISTS idx_claims_city ON claims(city);
CREATE INDEX IF NOT EXISTS idx_listings_city ON listings(city);
CREATE INDEX IF NOT EXISTS idx_auth_tokens_hash ON auth_tokens(token_hash);

-- Exclusion/moderation layer (non-destructive, reversible)
CREATE TABLE IF NOT EXISTS exclusions (
  fsa_id INTEGER PRIMARY KEY,
  reason TEXT NOT NULL,
  excluded_by TEXT NOT NULL,
  excluded_at TEXT NOT NULL DEFAULT (datetime('now')),
  restored_by TEXT,
  restored_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_exclusions_active ON exclusions(fsa_id) WHERE restored_at IS NULL;
