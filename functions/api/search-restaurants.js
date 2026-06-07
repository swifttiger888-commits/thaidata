// ThaiData UK — /api/search-restaurants?q=
// Lightweight restaurant autocomplete from our FSA-derived dataset.
// Returns top 10 matches: prefix-first, then substring, max 10 results.
const SEARCH_URL =
  'https://thaidata.uk/data/restaurants-search.json';

let searchIndex = null;

async function loadIndex() {
  if (searchIndex) return searchIndex;
  try {
    const res = await fetch(SEARCH_URL);
    searchIndex = await res.json();
  } catch {
    searchIndex = [];
  }
  return searchIndex;
}

export async function onRequestGet(context) {
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  const q = (context.request.url.match(/[?&]q=([^&]*)/i) || [])[1];
  if (!q || q.length < 2) {
    return new Response(JSON.stringify([]), { status: 200, headers: corsHeaders });
  }

  const needle = q.toLowerCase().replace(/[.+^${}()|[\]\\]/g, '');
  const index = await loadIndex();

  const prefix = [];
  const substring = [];

  for (const r of index) {
    const name = r.name.toLowerCase();
    if (name.startsWith(needle)) {
      prefix.push(r);
      if (prefix.length >= 10) break;
    }
  }

  if (prefix.length < 10) {
    for (const r of index) {
      const name = r.name.toLowerCase();
      if (name.includes(needle) && !name.startsWith(needle)) {
        substring.push(r);
        if (prefix.length + substring.length >= 10) break;
      }
    }
  }

  const results = [...prefix, ...substring].slice(0, 10);

  return new Response(JSON.stringify(results), {
    status: 200,
    headers: corsHeaders,
  });
}
