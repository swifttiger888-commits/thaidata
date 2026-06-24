// ThaiData UK — POST /api/enrichment
// Bulk import Google Places enrichment data into D1
// Called by the enrichment pipeline after Places API fetch

/**
 * Handles POST /api/enrichment — bulk upsert google_enrichment rows
 * Body: { entries: [{fsa_id, google_place_id, rating, review_count, ...}] }
 * Authorization: Bearer <ADMIN_PASSWORD> (same as admin API)
 * @param {object} context
 * @param {Request} context.request
 * @param {object} context.env - with DB binding and ADMIN_PASSWORD
 */
export async function onRequestPost(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  try {
    // Auth: same as admin — Bearer token = ADMIN_PASSWORD
    const auth = request.headers.get('Authorization');
    if (!auth || !auth.startsWith('Bearer ') || auth.slice(7) !== env.ADMIN_PASSWORD) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: corsHeaders,
      });
    }

    const body = await request.json();

    // -- Migration mode: create table if not exists --
    if (body.action === 'migrate') {
      try {
        await env.DB.prepare(`
          CREATE TABLE IF NOT EXISTS google_enrichment (
            fsa_id INTEGER PRIMARY KEY,
            google_place_id TEXT NOT NULL,
            rating REAL,
            review_count INTEGER,
            phone TEXT,
            website TEXT,
            opening_hours TEXT,
            photos TEXT,
            description TEXT,
            price_level TEXT,
            raw_response TEXT,
            fetched_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT
          )
        `).run();
        await env.DB.prepare(
          'CREATE INDEX IF NOT EXISTS idx_google_enrichment_place_id ON google_enrichment(google_place_id)'
        ).run();
        return new Response(JSON.stringify({ success: true, migrated: true }), {
          status: 200, headers: corsHeaders,
        });
      } catch (err) {
        return new Response(JSON.stringify({ error: err.message }), {
          status: 500, headers: corsHeaders,
        });
      }
    }

    const entries = body.entries;
    if (!Array.isArray(entries) || entries.length === 0) {
      return new Response(JSON.stringify({ error: 'entries array required' }), {
        status: 400,
        headers: corsHeaders,
      });
    }

    let inserted = 0;
    let updated = 0;
    const errors = [];

    for (const entry of entries) {
      try {
        const { fsa_id } = entry;
        if (!fsa_id) continue;

        // Check if row already exists
        const existing = await env.DB.prepare(
          'SELECT fsa_id FROM google_enrichment WHERE fsa_id = ?'
        ).bind(fsa_id).first();

        if (existing) {
          // Update
          await env.DB.prepare(`
            UPDATE google_enrichment SET
              google_place_id = ?,
              rating = ?,
              review_count = ?,
              phone = ?,
              website = ?,
              opening_hours = ?,
              photos = ?,
              description = ?,
              price_level = ?,
              raw_response = ?,
              fetched_at = datetime('now'),
              expires_at = ?
            WHERE fsa_id = ?
          `).bind(
            entry.google_place_id || null,
            entry.rating || null,
            entry.review_count || null,
            entry.phone || null,
            entry.website || null,
            entry.opening_hours || null,
            entry.photos || null,
            entry.description || null,
            entry.price_level || null,
            entry.raw_response || null,
            entry.expires_at || null,
            fsa_id
          ).run();
          updated++;
        } else {
          // Insert
          await env.DB.prepare(`
            INSERT INTO google_enrichment (
              fsa_id, google_place_id, rating, review_count,
              phone, website, opening_hours, photos,
              description, price_level, raw_response, fetched_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)
          `).bind(
            fsa_id,
            entry.google_place_id || null,
            entry.rating || null,
            entry.review_count || null,
            entry.phone || null,
            entry.website || null,
            entry.opening_hours || null,
            entry.photos || null,
            entry.description || null,
            entry.price_level || null,
            entry.raw_response || null,
            entry.expires_at || null
          ).run();
          inserted++;
        }
      } catch (err) {
        errors.push({ fsa_id: entry.fsa_id, error: err.message });
      }
    }

    return new Response(JSON.stringify({
      success: true,
      inserted,
      updated,
      errors: errors.length > 0 ? errors : undefined,
    }), {
      status: 200,
      headers: corsHeaders,
    });

  } catch (err) {
    console.error('Enrichment POST error:', err);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500,
      headers: corsHeaders,
    });
  }
}

/**
 * Handles GET /api/enrichment — read enrichment by fsa_id
 * Query: ?fsa_id=12345 or ?fsa_ids=123,456,789
 */
export async function onRequestGet(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  try {
    const url = new URL(request.url);
    const fsaId = url.searchParams.get('fsa_id');
    const fsaIds = url.searchParams.get('fsa_ids');

    if (fsaId) {
      const row = await env.DB.prepare(
        'SELECT * FROM google_enrichment WHERE fsa_id = ?'
      ).bind(parseInt(fsaId)).first();
      
      return new Response(JSON.stringify(row || null), {
        status: 200,
        headers: corsHeaders,
      });
    }

    if (fsaIds) {
      const ids = fsaIds.split(',').map(id => parseInt(id.trim())).filter(Boolean);
      if (ids.length === 0) {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: corsHeaders,
        });
      }
      const placeholders = ids.map(() => '?').join(',');
      const result = await env.DB.prepare(
        `SELECT * FROM google_enrichment WHERE fsa_id IN (${placeholders})`
      ).bind(...ids).all();
      
      return new Response(JSON.stringify(result.results), {
        status: 200,
        headers: corsHeaders,
      });
    }

    return new Response(JSON.stringify({ error: 'Provide fsa_id or fsa_ids' }), {
      status: 400,
      headers: corsHeaders,
    });

  } catch (err) {
    console.error('Enrichment GET error:', err);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500,
      headers: corsHeaders,
    });
  }
}
