// ThaiData UK — POST /api/upload
// Upload restaurant photos to Cloudflare Images
// Env var required: CF_IMAGES_API_TOKEN

const CF_ACCOUNT_ID = 'badd33ce94008f499f2ae75fd3b04574';
const CF_DELIVERY = 'https://imagedelivery.net/0mC63s07iTD25-GQ6n3_8A';
const CF_API = `https://api.cloudflare.com/client/v4/accounts/${CF_ACCOUNT_ID}/images/v1`;

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
    // --- Auth via magic link token ---
    const auth = request.headers.get('Authorization');
    if (!auth || !auth.startsWith('Bearer ')) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401, headers: corsHeaders,
      });
    }

    const rawToken = auth.slice(7);
    const tokenHash = await sha256(rawToken);
    const tokenRecord = await env.DB.prepare(
      "SELECT listing_id FROM auth_tokens WHERE token_hash = ? AND expires_at > datetime('now') AND used = 0"
    ).bind(tokenHash).first();

    if (!tokenRecord) {
      return new Response(JSON.stringify({ error: 'Invalid or expired token' }), {
        status: 403, headers: corsHeaders,
      });
    }

    const listingId = tokenRecord.listing_id;

    // --- Check Cloudflare Images API token ---
    const apiToken = env.CF_IMAGES_API_TOKEN;
    if (!apiToken) {
      return new Response(JSON.stringify({ error: 'Photo storage not configured. Add CF_IMAGES_API_TOKEN in Cloudflare Dashboard.' }), {
        status: 500, headers: corsHeaders,
      });
    }

    // --- Parse multipart form data ---
    const contentType = request.headers.get('Content-Type') || '';
    if (!contentType.includes('multipart/form-data')) {
      return new Response(JSON.stringify({ error: 'Expected multipart/form-data' }), {
        status: 400, headers: corsHeaders,
      });
    }

    const formData = await request.formData();
    const files = formData.getAll('photos');
    if (!files || files.length === 0) {
      return new Response(JSON.stringify({ error: 'No photos provided' }), {
        status: 400, headers: corsHeaders,
      });
    }

    const uploaded = [];
    const maxSize = 10 * 1024 * 1024; // 10MB per file
    const validTypes = ['image/jpeg', 'image/png', 'image/webp'];

    for (const file of files) {
      if (!file.name || !file.size) continue;
      if (!validTypes.includes(file.type)) continue;
      if (file.size > maxSize) continue;

      // Upload to Cloudflare Images API
      const cfForm = new FormData();
      cfForm.append('file', file);
      cfForm.append('metadata', JSON.stringify({ listing_id: listingId }));

      const cfRes = await fetch(CF_API, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${apiToken}` },
        body: cfForm,
      });

      const cfData = await cfRes.json();

      if (!cfRes.ok || !cfData.success) {
        console.error('CF Images upload failed:', JSON.stringify(cfData.errors));
        continue;
      }

      // URL pattern: https://imagedelivery.net/<hash>/<image_id>/<variant>
      const imageId = cfData.result.id;
      const url = `${CF_DELIVERY}/${imageId}/public`;
      uploaded.push(url);
    }

    if (uploaded.length === 0) {
      return new Response(JSON.stringify({ error: 'No valid photos uploaded. Max 10MB each, JPEG/PNG/WebP only.' }), {
        status: 400, headers: corsHeaders,
      });
    }

    // --- Append to listing's existing photos ---
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
      status: 200, headers: corsHeaders,
    });

  } catch (err) {
    console.error('Upload error:', err.message);
    return new Response(JSON.stringify({ error: 'Upload failed' }), {
      status: 500, headers: corsHeaders,
    });
  }
}

// --- Crypto helper ---
async function sha256(text) {
  const encoder = new TextEncoder();
  const data = encoder.encode(text);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(hash))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}
