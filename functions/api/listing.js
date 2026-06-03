// ThaiData UK — /api/listing
// Get and update enhanced restaurant listings

// GET /api/listing — get enhanced listing(s)
// Supports:
//   ?restaurant=X&city=Y  — specific listing
//   ?fsa_id=X             — by FSA ID
//   ?city=X               — all listings in a city
//   Authorization: Bearer <token>  — get listing by auth token (owner view)
export async function onRequestGet(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  try {
    const url = new URL(request.url);
    const auth = request.headers.get('Authorization');

    // Token-based auth: return listing for the authenticated owner
    if (auth && auth.startsWith('Bearer ')) {
      const tokenHash = auth.slice(7);
      const tokenRecord = await env.DB.prepare(
        "SELECT listing_id FROM auth_tokens WHERE token_hash = ? AND expires_at > datetime('now') AND used = 0"
      ).bind(tokenHash).first();

      if (!tokenRecord) {
        return new Response(JSON.stringify({ error: 'Invalid or expired token' }), {
          status: 403,
          headers: corsHeaders,
        });
      }

      const listing = await env.DB.prepare('SELECT * FROM listings WHERE id = ?').bind(tokenRecord.listing_id).first();
      if (!listing) {
        return new Response(JSON.stringify({ listings: [], count: 0 }), {
          status: 200,
          headers: corsHeaders,
        });
      }

      listing.features = listing.features ? JSON.parse(listing.features) : [];
      listing.photos = listing.photos ? JSON.parse(listing.photos) : [];

      return new Response(JSON.stringify({ listings: [listing], count: 1 }), {
        status: 200,
        headers: corsHeaders,
      });
    }

    // Public queries
    const restaurant = url.searchParams.get('restaurant');
    const city = url.searchParams.get('city');
    const fsaId = url.searchParams.get('fsa_id');

    let query = 'SELECT * FROM listings WHERE 1=1';
    const params = [];

    if (restaurant && city) {
      query += ' AND restaurant_name = ? AND city = ?';
      params.push(restaurant, city);
    } else if (fsaId) {
      query += ' AND fsa_id = ?';
      params.push(fsaId);
    } else if (city) {
      query += ' AND city = ?';
      params.push(city);
    } else {
      return new Response(JSON.stringify({ error: 'Provide restaurant+city, fsa_id, city, or auth token' }), {
        status: 400,
        headers: corsHeaders,
      });
    }

    const results = await env.DB.prepare(query).bind(...params).all();

    // Parse JSON fields
    const listings = results.results.map(l => ({
      ...l,
      features: l.features ? JSON.parse(l.features) : [],
      photos: l.photos ? JSON.parse(l.photos) : [],
    }));

    return new Response(JSON.stringify({ listings, count: listings.length }), {
      status: 200,
      headers: corsHeaders,
    });

  } catch (err) {
    console.error('Listing GET error:', err);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500,
      headers: corsHeaders,
    });
  }
}

// PUT /api/listing — update enhanced listing (owner only, via magic link token)
export async function onRequestPut(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  try {
    // Auth via magic link token
    const auth = request.headers.get('Authorization');
    if (!auth || !auth.startsWith('Bearer ')) {
      return new Response(JSON.stringify({ error: 'Unauthorized. Use your magic link to get a token.' }), {
        status: 401,
        headers: corsHeaders,
      });
    }

    const tokenHash = auth.slice(7);
    const tokenRecord = await env.DB.prepare(
      "SELECT listing_id, expires_at, used FROM auth_tokens WHERE token_hash = ? AND expires_at > datetime('now') AND used = 0"
    ).bind(tokenHash).first();

    if (!tokenRecord) {
      return new Response(JSON.stringify({ error: 'Invalid or expired token. Request a new magic link.' }), {
        status: 403,
        headers: corsHeaders,
      });
    }

    const body = await request.json();
    const allowedFields = [
      'description', 'cuisine_specialty', 'website', 'phone', 'email',
      'social_instagram', 'social_facebook', 'social_twitter',
      'address', 'postcode', 'opening_hours', 'price_range', 'features', 'photos'
    ];

    // Build SET clause from allowed fields
    const sets = [];
    const params = [];

    for (const field of allowedFields) {
      if (body[field] !== undefined) {
        sets.push(`${field} = ?`);
        // Stringify arrays/objects
        params.push(
          (field === 'features' || field === 'photos')
            ? JSON.stringify(body[field])
            : body[field]
        );
      }
    }

    if (sets.length === 0) {
      return new Response(JSON.stringify({ error: 'No valid fields to update' }), {
        status: 400,
        headers: corsHeaders,
      });
    }

    sets.push("updated_at = datetime('now')");
    params.push(tokenRecord.listing_id);

    await env.DB.prepare(
      `UPDATE listings SET ${sets.join(', ')} WHERE id = ?`
    ).bind(...params).run();

    // Mark token as used
    await env.DB.prepare(
      'UPDATE auth_tokens SET used = 1 WHERE token_hash = ?'
    ).bind(tokenHash).run();

    return new Response(JSON.stringify({
      success: true,
      message: 'Listing updated successfully. Get a new magic link to edit again.',
    }), {
      status: 200,
      headers: corsHeaders,
    });

  } catch (err) {
    console.error('Listing PUT error:', err);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500,
      headers: corsHeaders,
    });
  }
}

// POST /api/listing/request-link — request a magic link to edit listing
export async function onRequestPost(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  try {
    const body = await request.json();
    const { restaurant_name, city, email } = body;

    if (!restaurant_name || !city || !email) {
      return new Response(JSON.stringify({ error: 'restaurant_name, city, and email required' }), {
        status: 400,
        headers: corsHeaders,
      });
    }

    // Find the approved claim for this restaurant + email match
    const claim = await env.DB.prepare(
      "SELECT c.id as claim_id, c.claimer_email, l.id as listing_id FROM claims c LEFT JOIN listings l ON l.claim_id = c.id WHERE c.restaurant_name = ? AND c.city = ? AND c.claimer_email = ? AND c.claim_status = 'approved'"
    ).bind(restaurant_name, city, email).first();

    if (!claim) {
      return new Response(JSON.stringify({ error: 'No approved claim found for this restaurant and email combination' }), {
        status: 404,
        headers: corsHeaders,
      });
    }

    // Generate token
    const token = crypto.randomUUID();
    const tokenHash = token; // In production, hash this. For now, use directly.
    const expiresAt = new Date(Date.now() + 60 * 60 * 1000).toISOString(); // 1 hour

    await env.DB.prepare(
      'INSERT INTO auth_tokens (listing_id, token_hash, expires_at) VALUES (?, ?, ?)'
    ).bind(claim.listing_id, tokenHash, expiresAt).run();

    // In production: send email via MailChannels or similar
    // For now, return the link in the response
    const magicLink = `https://thaidata.uk/listing/manage?token=${tokenHash}`;

    return new Response(JSON.stringify({
      success: true,
      message: 'Magic link generated. Check your email (or use the link below in development).',
      magic_link: magicLink,
      expires: expiresAt,
    }), {
      status: 200,
      headers: corsHeaders,
    });

  } catch (err) {
    console.error('Magic link error:', err);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500,
      headers: corsHeaders,
    });
  }
}
