/**
 * ThaiData UK — MCP Server (Cloudflare Pages Function)
 * 
 * Model Context Protocol endpoint: https://thaidata.uk/mcp
 * Exposes ThaiData's UK Thai restaurant intelligence as AI-callable tools.
 * 
 * Protocol: JSON-RPC 2.0 over HTTP POST
 * Spec: https://modelcontextprotocol.io
 */

// ── Embedded data snapshot (updated via deploy pipeline) ──────────────
const EMBEDDED_DATA = {
  name: "ThaiData UK",
  description: "Business intelligence and cost defense tools for UK Thai restaurant operators",
  last_updated: "2026-06-03",
  statistics: {
    total_uk_thai_businesses: 1557,
    total_full_service_restaurants: 965,
    total_quick_service_takeaways: 592,
    uk_average_hygiene_rating: 4.1,
    uk_average_per_100k_density: 2.6,
    hygiene_rating_5_percentage: 50.4,
    estimated_uk_market_size_gbp: "£2.1B",
    growth_rate_2022_2025_pct: 20.3,
    national_living_wage_april_2026: 12.71,
    national_living_wage_18_20_april_2026: 10.85,
    national_living_wage_apprentice_april_2026: 8.00,
    average_delivery_commission_uber_eats_pct: 30,
    average_delivery_commission_deliveroo_pct: 32,
    average_delivery_commission_just_eat_pct: 14,
    typical_startup_cost_gbp: { min: 80000, max: 180000 },
    chef_visa_first_year_cost_gbp: { min: 8000, max: 15000 },
    chef_visa_min_salary_gbp: 38700,
    chef_visa_processing_weeks: { min: 12, max: 24 },
    opening_timeline_weeks: { realistic: { min: 22, max: 30 }, best_case: { min: 14, max: 18 }, worst_case: 36 }
  },
  cities: [
    { name: "London", total: 411, dine_in: 323, takeaway: 88, rating: 4.1, per_100k: 4.6, population: 8970000 },
    { name: "Leeds", total: 34, dine_in: 27, takeaway: 7, rating: 4.4, per_100k: 4.2, population: 812000 },
    { name: "Manchester", total: 28, dine_in: 24, takeaway: 4, rating: 4.1, per_100k: 4.9, population: 568000 },
    { name: "Edinburgh", total: 24, dine_in: 15, takeaway: 9, rating: 4.2, per_100k: 4.4, population: 548000 },
    { name: "Bristol", total: 19, dine_in: 15, takeaway: 4, rating: 4.6, per_100k: 3.9, population: 483000 },
    { name: "Birmingham", total: 17, dine_in: 15, takeaway: 2, rating: 4.4, per_100k: 1.5, population: 1166000 },
    { name: "Bradford", total: 15, dine_in: 10, takeaway: 5, rating: 3.8, per_100k: 2.7, population: 547000 },
    { name: "Leicester", total: 15, dine_in: 10, takeaway: 5, rating: 4.5, per_100k: 4.0, population: 374000 },
    { name: "Bournemouth", total: 14, dine_in: 11, takeaway: 3, rating: 4.7, per_100k: 3.5, population: 401000 },
    { name: "Swansea", total: 14, dine_in: 12, takeaway: 2, rating: 4.0, per_100k: 5.7, population: 247000 },
    { name: "Brighton", total: 13, dine_in: 12, takeaway: 1, rating: 4.8, per_100k: 4.7, population: 277000 },
    { name: "Sheffield", total: 13, dine_in: 12, takeaway: 1, rating: 4.6, per_100k: 2.2, population: 584000 },
    { name: "Glasgow", total: 8, dine_in: 5, takeaway: 3, rating: 5.0, per_100k: 1.3, population: 635000 }
  ],
  delivery_commissions: {
    "Uber Eats": { commission_pct: 30, markup_pct: 22, notes: "Plus 5-10% marketing add-on" },
    "Deliveroo": { commission_pct: 32, markup_pct: 22, notes: "Plus 5% service fee on some plans" },
    "Just Eat": { commission_pct: 14, markup_pct: 15, notes: "Lower base, but charges for card processing" }
  },
  opening_costs: {
    lease_deposit: { min: 8000, max: 25000, note: "3-6 months upfront" },
    refurbishment: { min: 30000, max: 80000, note: "Kitchen + dining area fit-out" },
    kitchen_equipment: { min: 15000, max: 40000, note: "Woks, fryers, refrigeration, extraction" },
    furniture_fixtures: { min: 8000, max: 20000, note: "Tables, chairs, bar, decor" },
    initial_stock: { min: 3000, max: 8000, note: "First month ingredients + dry goods" },
    licenses_legal: { min: 2000, max: 5000, note: "Alcohol license, food registration, solicitor" },
    branding_marketing: { min: 3000, max: 12000, note: "Signage, menu design, launch campaign" },
    working_capital: { min: 10000, max: 25000, note: "3 months operating costs buffer" }
  },
  key_dates_2026: {
    nlw_rise_effective: "2026-04-01",
    employment_allowance: 10500,
    employer_ni_threshold: 5000,
    employer_ni_rate_pct: 15.0,
    skilled_worker_visa_min_salary: 38700
  }
};

// ── Tool definitions (JSON Schema) ──────────────────────────────────
const TOOLS = [
  {
    name: "get_city_stats",
    description: "Get detailed Thai restaurant statistics for a specific UK city. Returns restaurant count, hygiene rating, density per 100k population, and breakdown of dine-in vs takeaway.",
    inputSchema: {
      type: "object",
      properties: {
        city: {
          type: "string",
          description: "UK city name (e.g. 'Leeds', 'Manchester', 'London', 'Edinburgh')"
        }
      },
      required: ["city"]
    }
  },
  {
    name: "get_uk_overview",
    description: "Get overall UK Thai restaurant market statistics: total businesses, market size, growth rate, average hygiene, and national wage data.",
    inputSchema: {
      type: "object",
      properties: {}
    }
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
    name: "get_opening_costs",
    description: "Get estimated cost breakdown for opening a Thai restaurant in the UK. Covers lease deposit, refurbishment, equipment, licenses, and working capital.",
    inputSchema: {
      type: "object",
      properties: {}
    }
  },
  {
    name: "get_delivery_rates",
    description: "Get current delivery platform commission rates for Uber Eats, Deliveroo, and Just Eat. Includes base commission and typical menu markup percentages.",
    inputSchema: {
      type: "object",
      properties: {}
    }
  },
  {
    name: "get_visa_info",
    description: "Get Skilled Worker visa costs and requirements for hiring Thai chefs. Includes minimum salary, processing times, and first-year cost estimates.",
    inputSchema: {
      type: "object",
      properties: {}
    }
  },
  {
    name: "rank_cities",
    description: "Rank UK cities by a given metric: total restaurants, hygiene rating, or density per 100k population. Returns top N cities.",
    inputSchema: {
      type: "object",
      properties: {
        metric: {
          type: "string",
          enum: ["total", "rating", "density"],
          description: "Metric to rank by: 'total' (restaurant count), 'rating' (avg hygiene), or 'density' (per 100k)"
        },
        limit: {
          type: "number",
          description: "Number of top cities to return (default: 5, max: 13)",
          default: 5
        }
      },
      required: ["metric"]
    }
  },
  {
    name: "get_market_health",
    description: "Get a summary assessment of the UK Thai restaurant market: competition level, growth trajectory, cost pressures, and key risks for operators.",
    inputSchema: {
      type: "object",
      properties: {}
    }
  }
];

// ── Helper: find city (case-insensitive fuzzy match) ────────────────
function findCity(name) {
  const query = name.toLowerCase().trim();
  // Exact match first
  let city = EMBEDDED_DATA.cities.find(c => c.name.toLowerCase() === query);
  // Prefix match
  if (!city) city = EMBEDDED_DATA.cities.find(c => c.name.toLowerCase().startsWith(query));
  // Contains match
  if (!city) city = EMBEDDED_DATA.cities.find(c => c.name.toLowerCase().includes(query));
  return city;
}

// ── Tool implementations ─────────────────────────────────────────────
const toolHandlers = {
  get_city_stats(params) {
    const city = findCity(params.city);
    if (!city) {
      return { error: `City '${params.city}' not found. Available: ${EMBEDDED_DATA.cities.map(c => c.name).join(', ')}` };
    }
    const marketSize = city.population < 500000 ? "small" : city.population < 1000000 ? "medium" : "large";
    return {
      city: city.name,
      population: city.population,
      thai_restaurants: { total: city.total, dine_in: city.dine_in, takeaway: city.takeaway },
      hygiene_rating: city.rating,
      density_per_100k: city.per_100k,
      market_size: marketSize,
      comparison_to_uk_avg: {
        density_vs_uk_avg: (city.per_100k / EMBEDDED_DATA.statistics.uk_average_per_100k_density * 100).toFixed(0) + '%',
        hygiene_vs_uk_avg: (city.rating / EMBEDDED_DATA.statistics.uk_average_hygiene_rating * 100).toFixed(0) + '%'
      }
    };
  },

  get_uk_overview() {
    const s = EMBEDDED_DATA.statistics;
    return {
      total_businesses: s.total_uk_thai_businesses,
      full_service: s.total_full_service_restaurants,
      quick_service: s.total_quick_service_takeaways,
      average_hygiene: s.uk_average_hygiene_rating,
      five_star_pct: s.hygiene_rating_5_percentage + '%',
      density_per_100k: s.uk_average_per_100k_density,
      estimated_market_size: s.estimated_uk_market_size_gbp,
      growth_2022_2025: s.growth_rate_2022_2025_pct + '%',
      cities_tracked: EMBEDDED_DATA.cities.length,
      data_freshness: EMBEDDED_DATA.last_updated
    };
  },

  compare_cities(params) {
    const c1 = findCity(params.city1);
    const c2 = findCity(params.city2);
    if (!c1) return { error: `City '${params.city1}' not found` };
    if (!c2) return { error: `City '${params.city2}' not found` };
    return {
      comparison: [params.city1, params.city2],
      [params.city1]: {
        population: c1.population, thai_total: c1.total, hygiene: c1.rating,
        density: c1.per_100k, dine_in: c1.dine_in, takeaway: c1.takeaway
      },
      [params.city2]: {
        population: c2.population, thai_total: c2.total, hygiene: c2.rating,
        density: c2.per_100k, dine_in: c2.dine_in, takeaway: c2.takeaway
      },
      differences: {
        population_ratio: (c1.population / c2.population).toFixed(2) + 'x',
        thai_count_diff: c1.total - c2.total,
        density_diff: (c1.per_100k - c2.per_100k).toFixed(1),
        hygiene_diff: (c1.rating - c2.rating).toFixed(1)
      }
    };
  },

  get_opening_costs() {
    const costs = EMBEDDED_DATA.opening_costs;
    let totalMin = 0, totalMax = 0;
    for (const k of Object.keys(costs)) {
      totalMin += costs[k].min;
      totalMax += costs[k].max;
    }
    // Add typical range
    const typical = EMBEDDED_DATA.statistics.typical_startup_cost_gbp;
    return {
      cost_breakdown: costs,
      total_range: { min: totalMin, max: totalMax },
      typical_range_industry: typical,
      note: "Costs vary significantly by location. London fit-outs run 30-50% higher on refurbishment and lease deposits."
    };
  },

  get_delivery_rates() {
    return {
      platforms: EMBEDDED_DATA.delivery_commissions,
      average_commission: EMBEDDED_DATA.statistics.average_delivery_commission_uber_eats_pct + '% (Uber Eats), ' +
        EMBEDDED_DATA.statistics.average_delivery_commission_deliveroo_pct + '% (Deliveroo), ' +
        EMBEDDED_DATA.statistics.average_delivery_commission_just_eat_pct + '% (Just Eat)',
      average_menu_markup: EMBEDDED_DATA.statistics.average_delivery_markup_pct + '%',
      tip: "Just Eat has the lowest commission but charges extra for card processing. Uber Eats and Deliveroo charge more but provide larger rider networks."
    };
  },

  get_visa_info() {
    const s = EMBEDDED_DATA.statistics;
    return {
      visa_type: "Skilled Worker Visa (SOC 5434 — Chefs)",
      minimum_salary: '£' + s.chef_visa_min_salary_gbp.toLocaleString(),
      first_year_cost_range: `£${s.chef_visa_first_year_cost_gbp.min.toLocaleString()} – £${s.chef_visa_first_year_cost_gbp.max.toLocaleString()}`,
      cost_includes: [
        "Certificate of Sponsorship (£239)",
        "Immigration Skills Charge (£1,000/year)",
        "Visa application fee (£719–£1,423)",
        "Immigration Health Surcharge (£1,035/year)",
        "Legal/agency fees if using solicitor"
      ],
      processing_time: `${s.chef_visa_processing_weeks.min}–${s.chef_visa_processing_weeks.max} weeks`,
      key_requirements: [
        "Job at RQF Level 3 or above (chef qualifies)",
        "English language B1 CEFR",
        "Employer must hold a valid Sponsor Licence",
        "Genuine vacancy test applies"
      ],
      more_info: "https://thaidata.uk/analysis/chef-visa-cliff"
    };
  },

  rank_cities(params) {
    const metric = params.metric || 'total';
    const limit = Math.min(params.limit || 5, 13);
    let sorted;
    if (metric === 'rating') {
      sorted = [...EMBEDDED_DATA.cities].sort((a, b) => b.rating - a.rating);
    } else if (metric === 'density') {
      sorted = [...EMBEDDED_DATA.cities].sort((a, b) => b.per_100k - a.per_100k);
    } else {
      sorted = [...EMBEDDED_DATA.cities].sort((a, b) => b.total - a.total);
    }
    const top = sorted.slice(0, limit);
    return {
      metric,
      rankings: top.map((c, i) => ({
        rank: i + 1,
        city: c.name,
        [metric === 'total' ? 'thai_restaurants' : metric === 'rating' ? 'hygiene_rating' : 'density_per_100k']:
          metric === 'total' ? c.total : metric === 'rating' ? c.rating : c.per_100k
      }))
    };
  },

  get_market_health() {
    const s = EMBEDDED_DATA.statistics;
    return {
      overall_assessment: "Growing market with moderate competition — 20.3% growth 2022-2025",
      competition_level: "Moderate. 1,557 businesses nationally. Density hotspots in Swansea (5.7/100k) and Manchester (4.9/100k). Birmingham underserved (1.5/100k) relative to population.",
      cost_pressures: [
        "NLW at £12.71/hr (up 6.7% from 2025) — labour is ~35% of revenue for typical Thai restaurant",
        "Employer NI rising to 15% from April 2026 on earnings above £5,000",
        "Ingredient costs volatile — Thai imports affected by GBP/THB exchange rate",
        "Delivery commissions eating 14-32% of order value"
      ],
      opportunities: [
        "Mid-sized cities underserved: Birmingham (1.5/100k), Sheffield (2.2/100k)",
        "High hygiene scores command premium pricing — Brighton avg 4.8 rating",
        "Menu engineering (GP optimization) can recover 3-5% margin",
        "Direct ordering (bypass delivery platforms) saves 14-32% per order"
      ],
      key_risks: [
        "Chef shortage — visa costs rising, processing 12-24 weeks",
        "Rate relief reduction from April 2026",
        "Consumer spending squeeze from higher mortgage/rent costs"
      ],
      data_confidence: "High — sourced from FSA FHRS (live feed), ONS population data, HMRC business counts"
    };
  }
};

// ── JSON-RPC 2.0 handler ─────────────────────────────────────────────
async function handleJSONRPC(request, env) {
  let body;
  try {
    body = await request.json();
  } catch {
    return jsonRPCError(null, -32700, "Parse error: invalid JSON");
  }

  const { jsonrpc, id, method, params } = body;

  // Validate JSON-RPC version
  if (jsonrpc !== "2.0") {
    return jsonRPCError(id, -32600, "Invalid Request: jsonrpc must be '2.0'");
  }

  // Handle notifications (no id) — we just ack silently
  if (id === undefined || id === null) {
    if (method === "notifications/initialized") {
      return new Response(null, { status: 202 });
    }
    return new Response(null, { status: 204 });
  }

  try {
    switch (method) {
      case "initialize":
        return jsonRPCResult(id, {
          protocolVersion: "2025-06-18",
          capabilities: {
            tools: {}
          },
          serverInfo: {
            name: "thaidata-uk-mcp",
            version: "1.0.0"
          }
        });

      case "tools/list":
        return jsonRPCResult(id, { tools: TOOLS });

      case "tools/call": {
        const { name, arguments: args } = params || {};
        if (!name) {
          return jsonRPCError(id, -32602, "Invalid params: 'name' is required");
        }
        const handler = toolHandlers[name];
        if (!handler) {
          return jsonRPCError(id, -32601, `Method not found: tool '${name}' is not registered`);
        }
        const result = handler(args || {});
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
  return new Response(JSON.stringify({
    jsonrpc: "2.0",
    id: id || null,
    error: { code, message }
  }), {
    status: 200,
    headers: { "Content-Type": "application/json" }
  });
}

// ── Cloudflare Pages Function exports ────────────────────────────────

// Handle CORS preflight
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

// Main MCP endpoint
export async function onRequestPost(context) {
  const { request } = context;
  const response = await handleJSONRPC(request, context.env);

  // Add CORS headers
  const newHeaders = new Headers(response.headers);
  newHeaders.set("Access-Control-Allow-Origin", "*");
  newHeaders.set("Access-Control-Allow-Methods", "POST, OPTIONS");
  newHeaders.set("Access-Control-Allow-Headers", "Content-Type, Authorization");

  return new Response(response.body, {
    status: response.status,
    headers: newHeaders
  });
}

// Also handle GET for discovery / health check
export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);

  // If it's a GET to /mcp, return server info for discovery
  return new Response(JSON.stringify({
    name: "ThaiData UK MCP Server",
    protocol: "Model Context Protocol (MCP)",
    version: "1.0.0",
    transport: "HTTP POST (JSON-RPC 2.0)",
    endpoint: "https://thaidata.uk/mcp",
    tools: TOOLS.length,
    tools_list: TOOLS.map(t => ({ name: t.name, description: t.description })),
    documentation: "https://modelcontextprotocol.io",
    usage: "Send JSON-RPC 2.0 requests via POST. First call 'initialize', then 'tools/list', then 'tools/call'.",
    example: 'curl -X POST https://thaidata.uk/mcp -H "Content-Type: application/json" -d \'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_city_stats","arguments":{"city":"Leeds"}}}\''
  }, null, 2), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*"
    }
  });
}
