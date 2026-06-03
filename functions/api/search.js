// ThaiData UK — GET /api/search?q=X&city=Y
// Proxy FSA API to avoid CORS, filtered to Thai restaurants only

export async function onRequestGet(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
    'Cache-Control': 'public, max-age=3600', // Cache for 1 hour
  };

  try {
    const url = new URL(request.url);
    const q = url.searchParams.get('q');
    const city = url.searchParams.get('city');
    const limit = parseInt(url.searchParams.get('limit') || '20');

    if (!q || q.length < 2) {
      return new Response(JSON.stringify({ error: 'Search query must be at least 2 characters' }), {
        status: 400,
        headers: corsHeaders,
      });
    }

    // Build FSA API URL — search establishments
    // The FSA API filters: BusinessType="Restaurant/Cafe/Canteen", and we search by name
    let fsaUrl = `https://api.ratings.food.gov.uk/Establishments?name=${encodeURIComponent(q)}&businessTypeId=1&pageSize=${limit}`;

    if (city) {
      // FSA doesn't have city filter in API v2, we'll filter post-fetch
      fsaUrl += `&localAuthorityId=&pageSize=50`;
    }

    const response = await fetch(fsaUrl, {
      headers: {
        'x-api-version': '2',
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`FSA API returned ${response.status}`);
    }

    const data = await response.json();
    let establishments = data.establishments || [];

    // Filter to only Thai cuisine
    establishments = establishments.filter(e => {
      const name = (e.BusinessName || '').toLowerCase();
      const type = (e.BusinessType || '').toLowerCase();
      // Match Thai in name, but exclude non-Thai false positives
      return (
        name.includes('thai') ||
        name.includes('siam') ||
        name.includes('bangkok') ||
        name.includes('chiang mai') ||
        name.includes('phuket') ||
        name.includes('sukhothai') ||
        name.includes('pad thai') ||
        name.includes('tom yum') ||
        (type.includes('thai') && !name.includes('wait') && !name.includes('ethio'))
      );
    });

    // If city filter, do post-filter on address
    if (city) {
      const cityLower = city.toLowerCase();
      establishments = establishments.filter(e => {
        const addr = [
          e.AddressLine1, e.AddressLine2, e.AddressLine3, e.AddressLine4, e.PostCode
        ].join(' ').toLowerCase();
        return addr.includes(cityLower);
      });
    }

    // Trim to limit
    establishments = establishments.slice(0, limit);

    // Map to clean format
    const results = establishments.map(e => ({
      id: e.FHRSID,
      name: e.BusinessName,
      address: [e.AddressLine1, e.AddressLine2, e.AddressLine3, e.AddressLine4].filter(Boolean).join(', '),
      postcode: e.PostCode,
      rating: e.RatingValue,
      rating_date: e.RatingDate,
      hygiene_score: e.scores?.Hygiene || null,
      structural_score: e.scores?.Structural || null,
      management_score: e.scores?.ConfidenceInManagement || null,
      business_type: e.BusinessType,
      local_authority: e.LocalAuthorityName,
      city: extractCity(e),
      url: `https://ratings.food.gov.uk/business/${e.FHRSID}`,
    }));

    return new Response(JSON.stringify({ results, count: results.length, query: q }), {
      status: 200,
      headers: corsHeaders,
    });

  } catch (err) {
    console.error('Search error:', err);
    return new Response(JSON.stringify({ error: 'Search failed', results: [] }), {
      status: 500,
      headers: corsHeaders,
    });
  }
}

function extractCity(establishment) {
  // Try to extract city from address fields
  const addressParts = [
    establishment.AddressLine1,
    establishment.AddressLine2,
    establishment.AddressLine3,
    establishment.AddressLine4,
  ].filter(Boolean);

  // Common UK cities
  const cities = [
    'London', 'Manchester', 'Birmingham', 'Leeds', 'Edinburgh', 'Glasgow',
    'Bristol', 'Liverpool', 'Sheffield', 'Newcastle', 'Nottingham', 'Leicester',
    'Brighton', 'Southampton', 'Portsmouth', 'Bournemouth', 'Cardiff', 'Belfast',
    'Oxford', 'Cambridge', 'York', 'Bath', 'Reading', 'Norwich', 'Aberdeen',
    'Dundee', 'Coventry', 'Hull', 'Stoke', 'Wolverhampton', 'Derby', 'Swansea',
  ];

  const fullAddress = addressParts.join(' ');

  for (const city of cities) {
    if (fullAddress.toLowerCase().includes(city.toLowerCase())) {
      return city;
    }
  }

  // Fall back to the last address line which often contains the city
  return addressParts[addressParts.length - 1] || '';
}
