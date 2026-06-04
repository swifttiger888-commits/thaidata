// ThaiData UK — POST /api/upload
// Upload restaurant photos to R2 bucket
// Requires R2 binding: env.PHOTOS

export async function onRequestPost(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  // CORS preflight
  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: corsHeaders });
  }

  try {
    // Auth via magic link token
    const auth = request.headers.get('Authorization');
    if (!auth || !auth.startsWith('Bearer ')) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: corsHeaders,
      });
    }

    // Verify token + get listing_id
    const rawToken = auth.slice(7);
    const tokenHash = await sha256(rawToken);
    const tokenRecord = await env.DB.prepare(
      "SELECT listing_id FROM auth_tokens WHERE token_hash = ? AND expires_at > datetime('now') AND used = 0"
    ).bind(tokenHash).first();

    if (!tokenRecord) {
      return new Response(JSON.stringify({ error: 'Invalid or expired token' }), {
        status: 403,
        headers: corsHeaders,
      });
    }

    const listingId = tokenRecord.listing_id;

    // Check R2 binding exists
    if (!env.PHOTOS) {
      return new Response(JSON.stringify({ error: 'Photo storage not configured. Add R2 binding in Cloudflare Dashboard.' }), {
        status: 500,
        headers: corsHeaders,
      });
    }

    // Parse multipart form data
    const contentType = request.headers.get('Content-Type') || '';
    if (!contentType.includes('multipart/form-data')) {
      return new Response(JSON.stringify({ error: 'Expected multipart/form-data' }), {
        status: 400,
        headers: corsHeaders,
      });
    }

    const formData = await request.formData();
    const files = formData.getAll('photos');
    if (!files || files.length === 0) {
      return new Response(JSON.stringify({ error: 'No photos provided' }), {
        status: 400,
        headers: corsHeaders,
      });
    }

    const uploaded = [];
    const maxSize = 5 * 1024 * 1024; // 5MB per file

    for (const file of files) {
      if (!file.name || !file.size) continue;

      // Validate type
      const validTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/avif', 'image/gif'];
      if (!validTypes.includes(file.type)) {
        continue;
      }

      // Validate size
      if (file.size > maxSize) {
        continue;
      }

      // Sanitize filename
      const ext = file.name.split('.').pop().toLowerCase().replace(/[^a-z0-9]/g, '');
      const safeName = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}.${ext}`;
      const key = `listings/${listingId}/${safeName}`;

      const arrayBuffer = await file.arrayBuffer();

      await env.PHOTOS.put(key, arrayBuffer, {
        httpMetadata: { contentType: file.type },
      });

      // Construct public URL — requires r2.dev domain or custom domain
      // Pattern: https://<bucket>.<account-id>.r2.cloudflarestorage.com/<key>
      // Or with custom domain: https://cdn.thaidata.uk/<key>
      // For now, use r2.dev if no custom domain configured
      const publicUrl = env.R2_PUBLIC_URL 
        ? `${env.R2_PUBLIC_URL}/${key}`
        : `https://pub-thaidata.r2.dev/${key}`;

      uploaded.push(publicUrl);
    }

    if (uploaded.length === 0) {
      return new Response(JSON.stringify({ error: 'No valid photos uploaded. Max 5MB each, JPEG/PNG/WebP/AVIF only.' }), {
        status: 400,
        headers: corsHeaders,
      });
    }

    // Append to listing's existing photos
    const listing = await env.DB.prepare('SELECT photos FROM listings WHERE id = ?').bind(listingId).first();
    const existingPhotos = listing && listing.photos ? JSON.parse(listing.photos) : [];
    const allPhotos = [...existingPhotos, ...uploaded];

    await env.DB.prepare(
      "UPDATE listings SET photos = ?, updated_at = datetime('now') WHERE id = ?"
    ).bind(JSON.stringify(allPhotos), listingId).run();

    return new Response(JSON.stringify({
      success: true,
      uploaded,
      total: allPhotos.length,
    }), {
      status: 200,
      headers: corsHeaders,
    });

  } catch (err) {
    console.error('Upload error:', err.message);
    return new Response(JSON.stringify({ error: 'Upload failed' }), {
      status: 500,
      headers: corsHeaders,
    });
  }
}

// --- Crypto helper (shared — same as listing.js) ---
async function sha256(text) {
  const encoder = new TextEncoder();
  const data = encoder.encode(text);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(hash))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}
