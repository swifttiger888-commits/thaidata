// ThaiData UK — DELETE /api/cleanup
// One-time endpoint to delete test claim #9
// Remove after use.

export async function onRequestDelete(context) {
  const { env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  try {
    const claimId = 9;
    
    // Delete listing
    await env.DB.prepare('DELETE FROM listings WHERE claim_id = ?').bind(claimId).run();
    // Delete orphaned auth tokens
    await env.DB.prepare('DELETE FROM auth_tokens WHERE listing_id NOT IN (SELECT id FROM listings)').run();
    // Delete claim
    await env.DB.prepare('DELETE FROM claims WHERE id = ?').bind(claimId).run();

    return new Response(JSON.stringify({
      success: true,
      message: 'Claim #9 and associated data deleted.',
    }), {
      status: 200, headers: corsHeaders,
    });

  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), {
      status: 500, headers: corsHeaders,
    });
  }
}
