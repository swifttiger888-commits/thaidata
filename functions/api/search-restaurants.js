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

  const url = new URL(context.request.url);
  const raw = url.searchParams.get('q');
  if (!raw || raw.length < 2) {
    return new Response(JSON.stringify([]), { status: 200, headers: corsHeaders });
  }

  const needle = raw.toLowerCase().replace(/[.+^${}()|[\]\\]/g, '');
  const index = await loadIndex();

  const prefix = [];

  for (const r of index) {
    const name = r.name.toLowerCase();
    if (name.startsWith(needle)) {
      prefix.push(r);
    }
  }

  // Score prefix matches: prefer names where the query is followed by
  // a clean word boundary, then in-word continuation (multi-word query),
  // then special chars. Tiebreak: shorter name = better.
  function score(name) {
    const rest = name.slice(needle.length);
    if (/^ [a-z]/.test(rest)) return 3;   // "Thai | Garden" — clean boundary
    if (/^[a-z]/.test(rest)) return 2;    // "Thai |dge" — in-word (multi-q)
    if (/^[ &0-9]/.test(rest)) return 1;  // "Thai & Pie", "Thai 1"
    return 0;
  }

  prefix.sort((a, b) => {
    const sa = score(a.name.toLowerCase());
    const sb = score(b.name.toLowerCase());
    if (sa !== sb) return sb - sa;
    if (a.name.length !== b.name.length) return a.name.length - b.name.length;
    return a.name.localeCompare(b.name);
  });

  // Fill remaining slots with substring matches
  const substring = [];
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
