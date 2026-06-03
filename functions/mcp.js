/**
 * ThaiData UK — MCP Server v2.0 (Cloudflare Pages Function)
 * 
 * Model Context Protocol endpoint: https://thaidata.uk/mcp
 * Exposes ThaiData's UK Thai restaurant intelligence as AI-callable tools.
 * 
 * v2: Dynamic data loading from static JSON APIs + named restaurant search
 * Protocol: JSON-RPC 2.0 over HTTP POST
 * Spec: https://modelcontextprotocol.io
 */

// ── Data loader (fetches from same origin, Cloudflare-internal, near-zero latency) ─
let citiesCache = null;
let restaurantsCache = null;
let cacheTime = 0;
const CACHE_TTL = 300000; // 5 minutes

async function getCities() {
  const now = Date.now();
  if (citiesCache && (now - cacheTime) < CACHE_TTL) return citiesCache;
  try {
    const res = await fetch('https://thaidata.uk/api/v1/cities.json');
    citiesCache = await res.json();
    cacheTime = now;
    return citiesCache;
  } catch (e) {
    // Fallback to embedded data
    return EMBEDDED_DATA;
  }
}

async function getRestaurants() {
  const now = Date.now();
  if (restaurantsCache && (now - cacheTime) < CACHE_TTL) return restaurantsCache;
  try {
    const res = await fetch('https://thaidata.uk/data/restaurants.json');
    restaurantsCache = await res.json();
    cacheTime = now;
    return restaurantsCache;
  } catch (e) {
    return { restaurants: [] };
  }
}

// ── Embedded fallback data ──────────────────────────────────────────
const EMBEDDED_DATA = {
  name: "ThaiData UK",
  cities: [
    { name: "London", population: 8970000, total_thai_businesses: 411, restaurants: 323, takeaways: 88, per_100k: 4.6, avg_hygiene_rating: 4.1 },
    { name: "Leeds", population: 812000, total_thai_businesses: 34, restaurants: 27, takeaways: 7, per_100k: 4.2, avg_hygiene_rating: 4.4 },
    { name: "Manchester", population: 568000, total_thai_businesses: 28, restaurants: 24, takeaways: 4, per_100k: 4.9, avg_hygiene_rating: 4.1 },
    { name: "Edinburgh", population: 548000, total_thai_businesses: 24, restaurants: 15, takeaways: 9, per_100k: 4.4, avg_hygiene_rating: 4.2 },
    { name: "Bristol", population: 483000, total_thai_businesses: 19, restaurants: 15, takeaways: 4, per_100k: 3.9, avg_hygiene_rating: 4.6 },
    { name: "Birmingham", population: 1166000, total_thai_businesses: 17, restaurants: 15, takeaways: 2, per_100k: 1.5, avg_hygiene_rating: 4.4 },
    { name: "Glasgow", population: 635000, total_thai_businesses: 8, restaurants: 5, takeaways: 3, per_100k: 1.3, avg_hygiene_rating: 5.0 }
  ],
  statistics: {
    total_uk_thai_businesses: 1649,
    estimated_uk_market_size_gbp: "£2.1B",
    growth_rate_2022_2025_pct: 20.3,
    national_living_wage_april_2026: 12.71,
    average_delivery_commission_uber_eats_pct: 30,
    average_delivery_commission_deliveroo_pct: 32,
    average_delivery_commission_just_eat_pct: 14,
    average_delivery_markup_pct: 22,
    typical_startup_cost_gbp: { min: 80000, max: 180000 },
    chef_visa_min_salary_gbp: 38700,
    chef_visa_processing_weeks: { min: 12, max: 24 }
  }
};

const DELIVERY_COMMISSIONS = {
  "Uber Eats": { commission_pct: 30, markup_pct: 22, notes: "Plus 5-10% marketing add-on" },
  "Deliveroo": { commission_pct: 32, markup_pct: 22, notes: "Plus 5% service fee on some plans" },
  "Just Eat": { commission_pct: 14, markup_pct: 15, notes: "Lower base, but charges for card processing" }
};

const OPENING_COSTS = {
  lease_deposit: { min: 8000, max: 25000, note: "3-6 months upfront" },
  refurbishment: { min: 30000, max: 80000, note: "Kitchen + dining area fit-out" },
  kitchen_equipment: { min: 15000, max: 40000, note: "Woks, fryers, refrigeration, extraction" },
  furniture_fixtures: { min: 8000, max: 20000, note: "Tables, chairs, bar, decor" },
  initial_stock: { min: 3000, max: 8000, note: "First month ingredients + dry goods" },
  licenses_legal: { min: 2000, max: 5000, note: "Alcohol license, food registration, solicitor" },
  branding_marketing: { min: 3000, max: 12000, note: "Signage, menu design, launch campaign" },
  working_capital: { min: 10000, max: 25000, note: "3 months operating costs buffer" }
};

// ── Tool definitions ─────────────────────────────────────────────────
const TOOLS = [
  {
    name: "get_city_stats",
    description: "Get detailed Thai restaurant statistics for any UK city. Returns restaurant count, hygiene rating, density per 100k population, dine-in vs takeaway breakdown, and market size classification.",
    inputSchema: {
      type: "object",
      properties: {
        city: { type: "string", description: "UK city name (e.g. 'Leeds', 'Manchester', 'London', 'Edinburgh', 'Bristol')" }
      },
      required: ["city"]
    }
  },
  {
    name: "search_restaurants",
    description: "Search individual Thai restaurants by city, type, or minimum hygiene rating. Returns named restaurants with address, postcode, rating, and inspection date. Perfect for finding top-rated Thai restaurants in any UK city.",
    inputSchema: {
      type: "object",
      properties: {
        city: { type: "string", description: "UK city name to search in" },
        type: { type: "string", enum: ["restaurant", "takeaway", "all"], description: "Filter by business type", default: "all" },
        min_rating: { type: "number", description: "Minimum hygiene rating (1-5). E.g. 4 returns only 4+ star rated." },
        max_hygiene_score: { type: "number", description: "Filter by FSA Hygiene score (0-25, lower=better). 0=perfect food handling." },
        max_structural_score: { type: "number", description: "Filter by FSA Structural score (0-25, lower=better). 0=perfect premises." },
        max_management_score: { type: "number", description: "Filter by FSA Management score (0-25, lower=better). 0=perfect systems/records." },
        limit: { type: "number", description: "Maximum results to return (default: 10, max: 50)", default: 10 }
      },
      required: ["city"]
    }
  },
  {
    name: "find_nearby",
    description: "Find Thai restaurants near a UK postcode. Geocodes the postcode, calculates driving distances, and returns the best-rated restaurants within your radius. Perfect for 'find Thai near me' queries.",
    inputSchema: {
      type: "object",
      properties: {
        postcode: { type: "string", description: "UK postcode to search near (e.g. 'LS1 4AG', 'SW1A 1AA', 'M1 1AE')" },
        radius: { type: "number", description: "Search radius in miles (default: 3, max: 25)", default: 3 },
        min_rating: { type: "number", description: "Minimum hygiene rating 1-5 (optional)" },
        max_hygiene_score: { type: "number", description: "FSA Hygiene score filter (0-25, 0=perfect)" },
        max_structural_score: { type: "number", description: "FSA Structural score filter (0-25, 0=perfect)" },
        max_management_score: { type: "number", description: "FSA Management score filter (0-25, 0=perfect)" },
        type: { type: "string", enum: ["restaurant", "takeaway", "all"], description: "Filter by type", default: "all" },
        limit: { type: "number", description: "Max results (default: 10, max: 25)", default: 10 }
      },
      required: ["postcode"]
    }
  },
  {
    name: "get_uk_overview",
    description: "Get overall UK Thai restaurant market statistics: total businesses, market size, growth rate, average hygiene, and national wage data.",
    inputSchema: { type: "object", properties: {} }
  },
  {
    name: "compare_cities",
    description: "Compare Thai restaurant statistics between two UK cities side by side.",
    inputSchema: {
      type: "object",
      properties: {
        city1: { type: "string", description: "First city name" },
        city2: { type: "string", description: "Second city name" }
      },
      required: ["city1", "city2"]
    }
  },
  {
    name: "rank_cities",
    description: "Rank UK cities by Thai restaurant count, hygiene rating, or density per 100k. Returns top N cities with full stats.",
    inputSchema: {
      type: "object",
      properties: {
        metric: { type: "string", enum: ["total", "rating", "density"], description: "Metric to rank by" },
        limit: { type: "number", description: "Number of cities to return (default: 10, max: 50)", default: 10 }
      },
      required: ["metric"]
    }
  },
  {
    name: "get_opening_costs",
    description: "Get estimated cost breakdown for opening a Thai restaurant in the UK: lease, refurbishment, equipment, licenses, and working capital.",
    inputSchema: { type: "object", properties: {} }
  },
  {
    name: "get_delivery_rates",
    description: "Get current delivery platform commission rates for Uber Eats (30%), Deliveroo (32%), and Just Eat (14%). Includes typical menu markups.",
    inputSchema: { type: "object", properties: {} }
  },
  {
    name: "get_visa_info",
    description: "Get Skilled Worker visa costs and requirements for hiring Thai chefs. Includes minimum salary (£38,700), processing times, and first-year cost estimates.",
    inputSchema: { type: "object", properties: {} }
  },
  {
    name: "get_market_health",
    description: "Get a comprehensive market health assessment: competition levels by city, cost pressures (wages, NI, ingredients), growth opportunities, and key risks for operators.",
    inputSchema: { type: "object", properties: {} }
  }
];

// ── Helpers ─────────────────────────────────────────────────────────
function findCity(cities, name) {
  const query = name.toLowerCase().trim();
  let city = cities.find(c => c.name.toLowerCase() === query);
  if (!city) city = cities.find(c => c.name.toLowerCase().startsWith(query));
  if (!city) city = cities.find(c => c.name.toLowerCase().includes(query));
  return city;
}

// ── Tool handlers ───────────────────────────────────────────────────
async function handleTool(name, args) {
  switch (name) {
    case "get_city_stats": return getCityStats(args);
    case "search_restaurants": return searchRestaurants(args);
    case "find_nearby": return findNearby(args);
    case "get_uk_overview": return getUKOverview(args);
    case "compare_cities": return compareCities(args);
    case "rank_cities": return rankCities(args);
    case "get_opening_costs": return getOpeningCosts(args);
    case "get_delivery_rates": return getDeliveryRates(args);
    case "get_visa_info": return getVisaInfo(args);
    case "get_market_health": return getMarketHealth(args);
    default: return { error: `Unknown tool: ${name}` };
  }
}

async function getCityStats(params) {
  const data = await getCities();
  const cities = data.cities || EMBEDDED_DATA.cities;
  const city = findCity(cities, params.city);
  if (!city) {
    const names = cities.slice(0, 10).map(c => c.name).join(', ');
    return { error: `City '${params.city}' not found. Try: ${names}... (${cities.length} cities tracked)` };
  }
  const pop = city.population || 0;
  const marketSize = pop < 200000 ? "small" : pop < 600000 ? "medium" : "large";
  return {
    city: city.name,
    population: pop,
    thai_restaurants: {
      total: city.total_thai_businesses || 0,
      dine_in: city.restaurants || 0,
      takeaway: city.takeaways || 0,
      takeaway_pct: city.total_thai_businesses ? Math.round((city.takeaways || 0) / city.total_thai_businesses * 100) + '%' : 'N/A'
    },
    hygiene_rating: city.avg_hygiene_rating || 'N/A',
    density_per_100k: city.per_100k || 'N/A',
    market_size: marketSize,
    source: "FSA FHRS + FHIS, updated " + (data.updated || "June 2026")
  };
}

async function searchRestaurants(params) {
  const data = await getRestaurants();
  let results = data.restaurants || [];
  
  // Filter by city
  if (params.city) {
    const cityLower = params.city.toLowerCase().trim();
    results = results.filter(r => {
      const rc = (r.city || '').toLowerCase();
      const rla = (r.local_authority || '').toLowerCase();
      return rc.includes(cityLower) || rla.includes(cityLower) || rc === cityLower;
    });
  }
  
  // Filter by type
  if (params.type && params.type !== 'all') {
    const typeFilter = params.type === 'takeaway' ? 'takeaway' : 'restaurant';
    results = results.filter(r => r.type === typeFilter);
  }
  
  // Filter by minimum rating
  if (params.min_rating) {
    const min = parseInt(params.min_rating);
    results = results.filter(r => {
      const rating = parseInt(r.hygiene_rating);
      return rating >= min;
    });
  }
  
  // Filter by FSA detail scores (lower is better, 0 = perfect)
  if (params.max_hygiene_score !== undefined) {
    const max = parseInt(params.max_hygiene_score);
    results = results.filter(r => {
      const s = parseInt(r.hygiene_score);
      return !isNaN(s) && s <= max;
    });
  }
  if (params.max_structural_score !== undefined) {
    const max = parseInt(params.max_structural_score);
    results = results.filter(r => {
      const s = parseInt(r.structural_score);
      return !isNaN(s) && s <= max;
    });
  }
  if (params.max_management_score !== undefined) {
    const max = parseInt(params.max_management_score);
    results = results.filter(r => {
      const s = parseInt(r.management_score);
      return !isNaN(s) && s <= max;
    });
  }
  
  // Sort by rating (highest first), then name
  results.sort((a, b) => {
    const ra = parseInt(a.hygiene_rating) || 0;
    const rb = parseInt(b.hygiene_rating) || 0;
    if (rb !== ra) return rb - ra;
    return (a.name || '').localeCompare(b.name || '');
  });
  
  const limit = Math.min(params.limit || 10, 50);
  const sliced = results.slice(0, limit);
  
  if (sliced.length === 0) {
    return { 
      results: [], 
      message: `No restaurants found matching criteria. Try a broader search. ${results.length} total restaurants in database.`
    };
  }
  
  return {
    total_matches: results.length,
    showing: sliced.length,
    restaurants: sliced.map(r => ({
      name: r.name,
      type: r.type,
      city: r.city,
      postcode: r.postcode,
      hygiene_rating: r.hygiene_rating + '/5',
      detail_scores: {
        hygiene_food_handling: r.hygiene_score != null ? r.hygiene_score + '/25 (lower=better)' : 'N/A',
        structural_cleanliness: r.structural_score != null ? r.structural_score + '/25 (lower=better)' : 'N/A',
        management_confidence: r.management_score != null ? r.management_score + '/25 (lower=better)' : 'N/A'
      },
      last_inspected: r.rating_date,
      address: r.address
    })),
    summary: `${results.length} restaurants found. Top result: ${sliced[0]?.name} (${sliced[0]?.hygiene_rating}★) in ${sliced[0]?.city}.`
  };
}

// ── Haversine distance (miles) ──────────────────────────────────────
function toRad(deg) { return deg * Math.PI / 180; }

function haversineMiles(lat1, lng1, lat2, lng2) {
  const R = 3959; // Earth radius in miles
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
            Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
            Math.sin(dLng/2) * Math.sin(dLng/2);
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// ── find_nearby tool ────────────────────────────────────────────────
async function findNearby(params) {
  const postcode = (params.postcode || '').trim();
  if (!postcode) return { error: "Postcode is required. E.g. 'LS1 4AG'" };
  
  const radius = Math.min(params.radius || 3, 25);
  const limit = Math.min(params.limit || 10, 25);
  
  // Step 1: Geocode the input postcode
  let originLat, originLng;
  try {
    const geoResp = await fetch(`https://api.postcodes.io/postcodes/${encodeURIComponent(postcode)}`);
    const geoData = await geoResp.json();
    if (!geoData.result) {
      return { error: `Could not find postcode '${postcode}'. Check the format (e.g. 'LS1 4AG').` };
    }
    originLat = geoData.result.latitude;
    originLng = geoData.result.longitude;
  } catch (e) {
    return { error: `Geocoding failed for '${postcode}'. Try a different postcode.` };
  }
  
  // Step 2: Load restaurants with coordinates
  const data = await getRestaurants();
  let results = (data.restaurants || []).filter(r => r.latitude && r.longitude);
  
  // Step 3: Calculate distances
  results = results.map(r => {
    const miles = haversineMiles(originLat, originLng, r.latitude, r.longitude);
    return { ...r, distance_miles: Math.round(miles * 10) / 10 };
  });
  
  // Step 4: Filter by radius
  results = results.filter(r => r.distance_miles <= radius);
  
  // Step 5: Apply optional filters
  if (params.type && params.type !== 'all') {
    results = results.filter(r => r.type === params.type);
  }
  if (params.min_rating) {
    const min = parseInt(params.min_rating);
    results = results.filter(r => {
      const rating = parseInt(r.hygiene_rating);
      return rating >= min;
    });
  }
  
  // Filter by FSA detail scores
  if (params.max_hygiene_score !== undefined) {
    const max = parseInt(params.max_hygiene_score);
    results = results.filter(r => {
      const s = parseInt(r.hygiene_score);
      return !isNaN(s) && s <= max;
    });
  }
  if (params.max_structural_score !== undefined) {
    const max = parseInt(params.max_structural_score);
    results = results.filter(r => {
      const s = parseInt(r.structural_score);
      return !isNaN(s) && s <= max;
    });
  }
  if (params.max_management_score !== undefined) {
    const max = parseInt(params.max_management_score);
    results = results.filter(r => {
      const s = parseInt(r.management_score);
      return !isNaN(s) && s <= max;
    });
  }
  
  // Step 6: Sort by distance, then rating
  results.sort((a, b) => {
    if (a.distance_miles !== b.distance_miles) return a.distance_miles - b.distance_miles;
    return (parseInt(b.hygiene_rating) || 0) - (parseInt(a.hygiene_rating) || 0);
  });
  
  const total = results.length;
  const sliced = results.slice(0, limit);
  
  if (sliced.length === 0) {
    return {
      search: { postcode, radius_miles: radius },
      results: [],
      message: `No Thai restaurants found within ${radius} miles of ${postcode}. Try increasing the radius.`
    };
  }
  
  return {
    search: { postcode, radius_miles: radius, origin: `${originLat}, ${originLng}` },
    total_within_radius: total,
    showing: sliced.length,
    restaurants: sliced.map(r => ({
      name: r.name,
      type: r.type,
      distance: r.distance_miles + ' mi',
      hygiene_rating: r.hygiene_rating + '/5',
      detail_scores: {
        hygiene_food_handling: r.hygiene_score != null ? r.hygiene_score + '/25 (lower=better)' : 'N/A',
        structural_cleanliness: r.structural_score != null ? r.structural_score + '/25 (lower=better)' : 'N/A',
        management_confidence: r.management_score != null ? r.management_score + '/25 (lower=better)' : 'N/A'
      },
      postcode: r.postcode,
      city: r.city,
      address: r.address,
      last_inspected: r.rating_date
    })),
    summary: `${total} Thai restaurants within ${radius} miles of ${postcode}. Closest: ${sliced[0]?.name} (${sliced[0]?.distance_miles} mi, ${sliced[0]?.hygiene_rating}★).`
  };
}

async function getUKOverview() {
  const data = await getCities();
  const cities = data.cities || EMBEDDED_DATA.cities;
  const total = cities.reduce((s, c) => s + (c.total_thai_businesses || 0), 0);
  const dineIn = cities.reduce((s, c) => s + (c.restaurants || 0), 0);
  const takeaway = cities.reduce((s, c) => s + (c.takeaways || 0), 0);
  const avgHygiene = cities.length > 0 
    ? (cities.reduce((s, c) => s + (c.avg_hygiene_rating || 0), 0) / cities.length).toFixed(1)
    : 'N/A';
  
  return {
    total_businesses: total,
    full_service_restaurants: dineIn,
    quick_service_takeaways: takeaway,
    average_hygiene: avgHygiene,
    estimated_market_size: EMBEDDED_DATA.statistics.estimated_uk_market_size_gbp,
    growth_2022_2025: EMBEDDED_DATA.statistics.growth_rate_2022_2025_pct + '%',
    cities_tracked: cities.length,
    data_updated: data.updated || "June 2026",
    national_living_wage: '£' + EMBEDDED_DATA.statistics.national_living_wage_april_2026 + '/hr'
  };
}

async function compareCities(params) {
  const data = await getCities();
  const cities = data.cities || EMBEDDED_DATA.cities;
  const c1 = findCity(cities, params.city1);
  const c2 = findCity(cities, params.city2);
  if (!c1) return { error: `City '${params.city1}' not found` };
  if (!c2) return { error: `City '${params.city2}' not found` };
  
  return {
    comparison: [params.city1, params.city2],
    [params.city1]: summarize(c1),
    [params.city2]: summarize(c2),
    differences: {
      population_ratio: (c1.population && c2.population) ? (c1.population / c2.population).toFixed(2) + 'x' : 'N/A',
      thai_count_diff: (c1.total_thai_businesses || 0) - (c2.total_thai_businesses || 0),
      density_diff: (c1.per_100k && c2.per_100k) ? (c1.per_100k - c2.per_100k).toFixed(1) + '/100k' : 'N/A',
      hygiene_diff: (c1.avg_hygiene_rating && c2.avg_hygiene_rating) ? (c1.avg_hygiene_rating - c2.avg_hygiene_rating).toFixed(1) + '★' : 'N/A'
    }
  };
}

function summarize(c) {
  return {
    population: c.population,
    thai_total: c.total_thai_businesses || 0,
    dine_in: c.restaurants || 0,
    takeaway: c.takeaways || 0,
    hygiene: c.avg_hygiene_rating || 'N/A',
    density_per_100k: c.per_100k || 'N/A'
  };
}

async function rankCities(params) {
  const data = await getCities();
  let cities = [...(data.cities || EMBEDDED_DATA.cities)];
  const metric = params.metric || 'total';
  const limit = Math.min(params.limit || 10, 50);
  
  if (metric === 'rating') {
    cities.sort((a, b) => (b.avg_hygiene_rating || 0) - (a.avg_hygiene_rating || 0));
  } else if (metric === 'density') {
    cities.sort((a, b) => (b.per_100k || 0) - (a.per_100k || 0));
  } else {
    cities.sort((a, b) => (b.total_thai_businesses || 0) - (a.total_thai_businesses || 0));
  }
  
  const top = cities.slice(0, limit);
  return {
    metric,
    rankings: top.map((c, i) => ({
      rank: i + 1,
      city: c.name,
      thai_restaurants: c.total_thai_businesses || 0,
      hygiene: c.avg_hygiene_rating || 'N/A',
      density: c.per_100k || 'N/A',
      population: c.population || 'N/A'
    }))
  };
}

async function getOpeningCosts() {
  let totalMin = 0, totalMax = 0;
  for (const k of Object.keys(OPENING_COSTS)) {
    totalMin += OPENING_COSTS[k].min;
    totalMax += OPENING_COSTS[k].max;
  }
  return {
    cost_breakdown: OPENING_COSTS,
    total_range: { min: totalMin, max: totalMax },
    typical_range_industry: EMBEDDED_DATA.statistics.typical_startup_cost_gbp,
    note: "London fit-outs run 30-50% higher on refurbishment and lease deposits."
  };
}

function getDeliveryRates() {
  return {
    platforms: DELIVERY_COMMISSIONS,
    average_menu_markup: EMBEDDED_DATA.statistics.average_delivery_markup_pct + '%',
    tip: "Just Eat has the lowest commission but charges for card processing. Direct ordering bypasses all commission."
  };
}

function getVisaInfo() {
  const s = EMBEDDED_DATA.statistics;
  return {
    visa_type: "Skilled Worker Visa (SOC 5434 — Chefs)",
    minimum_salary: '£' + s.chef_visa_min_salary_gbp.toLocaleString(),
    processing_time: `${s.chef_visa_processing_weeks.min}–${s.chef_visa_processing_weeks.max} weeks`,
    cost_includes: [
      "Certificate of Sponsorship (£239)",
      "Immigration Skills Charge (£1,000/year)",
      "Visa application fee (£719–£1,423)",
      "Immigration Health Surcharge (£1,035/year)",
      "Legal/agency fees if using solicitor"
    ],
    key_requirements: [
      "Job at RQF Level 3 or above (chef qualifies)",
      "English language B1 CEFR",
      "Employer must hold valid Sponsor Licence",
      "Genuine vacancy test applies"
    ],
    more_info: "https://thaidata.uk/analysis/chef-visa-cliff"
  };
}

async function getMarketHealth() {
  const data = await getCities();
  const cities = data.cities || EMBEDDED_DATA.cities;
  const total = cities.reduce((s, c) => s + (c.total_thai_businesses || 0), 0);
  
  // Find most and least dense cities
  const withDensity = cities.filter(c => c.per_100k && c.population > 100000);
  withDensity.sort((a, b) => (b.per_100k || 0) - (a.per_100k || 0));
  const mostDense = withDensity.slice(0, 3);
  const leastDense = withDensity.reverse().slice(0, 3);
  
  return {
    overall_assessment: `Growing market — ${total}+ Thai businesses across ${cities.length} UK cities`,
    competition_hotspots: mostDense.map(c => `${c.name} (${c.per_100k}/100k, ${c.total_thai_businesses} restaurants)`),
    underserved_cities: leastDense.map(c => `${c.name} (${c.per_100k}/100k, pop ${(c.population||0).toLocaleString()})`),
    cost_pressures: [
      "NLW £12.71/hr — labour is ~35% of revenue",
      "Employer NI rising to 15% on earnings above £5,000",
      "Delivery commissions eating 14-32% per order",
      "Ingredient costs volatile — GBP/THB dependent"
    ],
    opportunities: [
      "Underserved mid-size cities with growing populations",
      "High hygiene scores command premium pricing",
      "Direct ordering saves 14-32% per order vs platforms",
      "Menu GP optimization can recover 3-5% margin"
    ],
    key_risks: [
      "Chef shortage — visa costs rising, processing 12-24 weeks",
      "Consumer spending squeeze from higher living costs",
      "Rate relief reduction from April 2026"
    ]
  };
}

// ── JSON-RPC 2.0 protocol ──────────────────────────────────────────
async function handleJSONRPC(request) {
  let body;
  try { body = await request.json(); }
  catch { return jsonRPCError(null, -32700, "Parse error: invalid JSON"); }

  const { jsonrpc, id, method, params } = body;
  if (jsonrpc !== "2.0") return jsonRPCError(id, -32600, "Invalid Request");

  // Notifications (no id)
  if (id === undefined || id === null) {
    if (method === "notifications/initialized") return new Response(null, { status: 202 });
    return new Response(null, { status: 204 });
  }

  try {
    switch (method) {
      case "initialize":
        return jsonRPCResult(id, {
          protocolVersion: "2025-06-18",
          capabilities: { tools: {} },
          serverInfo: { name: "thaidata-uk-mcp", version: "2.0.0" }
        });

      case "tools/list":
        return jsonRPCResult(id, { tools: TOOLS });

      case "tools/call": {
        const { name, arguments: args } = params || {};
        if (!name) return jsonRPCError(id, -32602, "Invalid params: 'name' required");
        const result = await handleTool(name, args || {});
        if (result.error) {
          return jsonRPCResult(id, { content: [{ type: "text", text: result.error }], isError: true });
        }
        return jsonRPCResult(id, { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] });
      }

      case "ping":
        return jsonRPCResult(id, {});

      default:
        return jsonRPCError(id, -32601, `Method not found: '${method}'`);
    }
  } catch (err) {
    return jsonRPCError(id, -32603, `Internal error: ${err.message}`);
  }
}

function jsonRPCResult(id, result) {
  return new Response(JSON.stringify({ jsonrpc: "2.0", id, result }), {
    status: 200,
    headers: { "Content-Type": "application/json" }
  });
}

function jsonRPCError(id, code, message) {
  return new Response(JSON.stringify({ jsonrpc: "2.0", id: id || null, error: { code, message } }), {
    status: 200,
    headers: { "Content-Type": "application/json" }
  });
}

// ── Cloudflare Pages Function exports ───────────────────────────────
export async function onRequestOptions() {
  return new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
      "Access-Control-Max-Age": "86400"
    }
  });
}

export async function onRequestPost(context) {
  const response = await handleJSONRPC(context.request);
  const headers = new Headers(response.headers);
  headers.set("Access-Control-Allow-Origin", "*");
  headers.set("Access-Control-Allow-Methods", "POST, OPTIONS");
  headers.set("Access-Control-Allow-Headers", "Content-Type, Authorization");
  return new Response(response.body, { status: response.status, headers });
}

export async function onRequest() {
  return new Response(JSON.stringify({
    name: "ThaiData UK MCP Server v2.0",
    protocol: "Model Context Protocol (MCP) — JSON-RPC 2.0",
    endpoint: "https://thaidata.uk/mcp",
    version: "2.0.0",
    tools: TOOLS.length,
    tools_list: TOOLS.map(t => ({ name: t.name, description: t.description.split('.')[0] })),
    data_sources: ["FSA FHRS", "FSA FHIS", "ONS", "HMRC"],
    new_in_v2: "Named restaurant search, all UK cities, dynamic data loading from live API",
    documentation: "https://modelcontextprotocol.io",
    example: 'curl -X POST https://thaidata.uk/mcp -H "Content-Type: application/json" -d \'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"search_restaurants","arguments":{"city":"Leeds","min_rating":4}}}\''
  }, null, 2), {
    status: 200,
    headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
  });
}
