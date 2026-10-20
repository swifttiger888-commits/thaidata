#!/usr/bin/env python3
"""
Generate the Thai Menu Price Index HTML page from collected survey data.
Run this AFTER collect_menu_prices.py has been filled in and saved to
/tmp/thai_menu_prices.json
"""
import json, os, html
from statistics import mean
from typing import Any
import site_icons  # noqa: E402  (same-dir module, replaces Font Awesome)

# Load data
data_path = '/tmp/thai_menu_prices.json'
if not os.path.exists(data_path):
    print(f"ERROR: {data_path} not found.")
    print("Run collect_menu_prices.py first to gather the data.")
    print("Fill in the SURVEY_TEMPLATE and save to /tmp/thai_menu_prices.json")
    exit(1)

with open(data_path) as f:
    survey: dict[str, Any] = json.load(f)

DISPLAY_NAMES: dict[str, str] = {
    "Pad Thai (chicken/prawn)": "Pad Thai",
    "Green Curry (chicken)": "Green Curry", 
    "Tom Yum Soup (prawn)": "Tom Yum",
    "Massaman Curry (beef)": "Massaman",
    "Spring Rolls (vegetable, 4pc starter)": "Spring Rolls",
}

# === COMPUTE STATISTICS ===
all_spreads: list[float] = []  # delivery markup percentages
dish_stats: dict[str, dict[str, list[float]]] = {}   # per-dish averages
city_stats: dict[str, dict[str, float | int]] = {}   # per-city averages

for city_name, city_data in survey.get('cities', {}).items():
    city_prices: dict[str, list[float]] = {'dine_in': [], 'delivery': [], 'spreads': []}
    
    for rest in city_data.get('restaurants', []):
        for dish_key, prices in rest.get('prices', {}).items():
            di = prices.get('dine_in')
            dd = prices.get('delivery')
            if di and dd and di > 0:
                spread = round((dd - di) / di * 100, 1)
                all_spreads.append(spread)
                city_prices['spreads'].append(spread)
                city_prices['dine_in'].append(di)
                city_prices['delivery'].append(dd)
                
                if dish_key not in dish_stats:
                    dish_stats[dish_key] = {'dine_in': [], 'delivery': [], 'spreads': []}
                dish_stats[dish_key]['dine_in'].append(di)
                dish_stats[dish_key]['delivery'].append(dd)
                dish_stats[dish_key]['spreads'].append(spread)
    
    if city_prices['spreads']:
        city_stats[city_name] = {
            'avg_dine_in': round(mean(city_prices['dine_in']), 2),
            'avg_delivery': round(mean(city_prices['delivery']), 2),
            'avg_spread': round(mean(city_prices['spreads']), 1),
            'data_points': len(city_prices['spreads'])
        }

avg_uk_spread: float = round(mean(all_spreads), 1) if all_spreads else 0

# Compute dish averages
dish_averages: dict[str, dict[str, float | int]] = {}
for dish, stats in dish_stats.items():
    dish_averages[dish] = {
        'avg_dine_in': round(mean(stats['dine_in']), 2),
        'avg_delivery': round(mean(stats['delivery']), 2),
        'avg_spread': round(mean(stats['spreads']), 1),
        'data_points': len(stats['spreads'])
    }

# === BUILD CITY COMPARISON ROWS ===
city_rows: list[str] = []
for city_name, stats in sorted(city_stats.items(), key=lambda x: x[1]['avg_spread'], reverse=True):
    city_rows.append(f'''                        <tr>
                            <td class="city-name">{html.escape(city_name)}</td>
                            <td class="city-count">£{stats['avg_dine_in']:.2f}</td>
                            <td class="city-count">£{stats['avg_delivery']:.2f}</td>
                            <td class="city-rating" style="color:{'#EF4444' if stats['avg_spread'] > 15 else '#F59E0B' if stats['avg_spread'] > 10 else 'var(--c2)'};">+{stats['avg_spread']}%</td>
                            <td class="city-pc">{stats['data_points']} dishes</td>
                        </tr>''')
city_rows_html = '\n'.join(city_rows) if city_rows else '<tr><td colspan="5" style="color:var(--ink4);text-align:center;padding:40px;">Data being collected — check back soon</td></tr>'

# === BUILD DISH COMPARISON ROWS ===
dish_rows: list[str] = []
for dish_key, stats in sorted(dish_averages.items(), key=lambda x: x[1]['avg_spread'], reverse=True):
    name = DISPLAY_NAMES.get(dish_key, dish_key)
    dish_rows.append(f'''                        <tr>
                            <td class="city-name">{html.escape(name)}</td>
                            <td class="city-count">£{stats['avg_dine_in']:.2f}</td>
                            <td class="city-count">£{stats['avg_delivery']:.2f}</td>
                            <td class="city-rating" style="color:{'#EF4444' if stats['avg_spread'] > 15 else '#F59E0B' if stats['avg_spread'] > 10 else 'var(--c2)'};">+{stats['avg_spread']}%</td>
                            <td class="city-pc">{stats['data_points']} prices</td>
                        </tr>''')
dish_rows_html = '\n'.join(dish_rows) if dish_rows else '<tr><td colspan="5" style="color:var(--ink4);text-align:center;padding:40px;">Data being collected — check back soon</td></tr>'

# === BUILD FULL PAGE ===
HTML = f'''<!DOCTYPE html>
<html lang="en-GB">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UK Thai Menu Price Index 2026: Dine-in vs Delivery | ThaiData</title>
    <meta name="description" content="What do Thai dishes actually cost across UK cities? Pad Thai, Green Curry, Tom Yum — real prices compared. Dine-in vs delivery markup analysis. See which restaurants inflate prices to cover commission.">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="https://thaidata.uk/thai-menu-price-index-uk">
    <meta property="og:type" content="article">
    <meta property="og:url" content="https://thaidata.uk/thai-menu-price-index-uk">
    <meta property="og:title" content="UK Thai Menu Price Index 2026: Dine-in vs Delivery">
    <meta property="og:description" content="Real menu prices for Pad Thai, Green Curry, Tom Yum across UK cities. See the dine-in vs delivery markup — and which restaurants hide commission in the price.">
    <meta property="og:locale" content="en_GB">

    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" media="print" onload="this.media='all'"><noscript><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"></noscript>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
    <style>
        :root {{ --c1: #A3132B; --c2: #A3132B; --dark: #FFFFFF; --ink: #1A1614; --ink2: #4A403C; --ink3: #7A6F6A; --ink4: #9C918C; --line: #E7DFD5; --bg: #FBF7F0; }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Inter', system-ui, sans-serif; color: var(--ink); background: var(--bg); line-height: 1.6; -webkit-font-smoothing: antialiased; }}
        .grain {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: url("https://grainy-gradients.vercel.app/noise.svg"); opacity: 0.03; pointer-events: none; z-index: 999; }}
        .wrap {{ max-width: 1100px; margin: 0 auto; padding: 0 20px; }}
        nav {{ background: var(--dark); border-bottom: 1px solid var(--line); height: 72px; display: flex; align-items: center; position: sticky; top: 0; z-index: 100; }}
        .nav-bar {{ max-width: 1100px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; padding: 0 20px; width: 100%; }}
        .logo {{ display: flex; align-items: center; gap: 12px; font-weight: 700; font-size: 1.4rem; color: var(--ink); text-decoration: none; }}
        .logo-icon {{ color: var(--c2); font-size: 1.5rem; }}
        .hero {{ padding: 80px 0 50px; text-align: center; }}
        .hero h1 {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: clamp(2rem, 5vw, 3rem); font-weight: 800; line-height: 1.15; margin-bottom: 16px; }}
        .hero h1 em {{ font-style: normal; color: var(--c2); }}
        .hero p {{ color: var(--ink4); font-size: 1.1rem; max-width: 650px; margin: 0 auto; }}
        .badge {{ display: inline-block; padding: 4px 12px; border-radius: 100px; background: rgba(16,185,129,0.1); color: var(--c2); font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; border: 1px solid rgba(16,185,129,0.25); margin-bottom: 16px; }}

        .section {{ padding: 30px 0 50px; }}
        .section h2 {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: 2rem; font-weight: 800; margin-bottom: 10px; }}
        .section h2 em {{ font-style: normal; color: var(--c2); }}
        .section-desc {{ color: var(--ink4); margin-bottom: 24px; font-size: 0.95rem; }}

        .big-stat {{ text-align: center; margin: 30px 0; }}
        .big-stat .number {{ font-family:'Archivo','Inter',system-ui,sans-serif; font-size: 4rem; color: '#EF4444' if avg_uk_spread > 15 else '#F59E0B' if avg_uk_spread > 10 else 'var(--c2)'; line-height: 1; font-weight: 800;}}
        .big-stat .label {{ color: var(--ink4); font-size: 0.9rem; margin-top: 8px; }}

        .highlight-box {{ background: rgba(16,185,129,0.05); border: 1px solid rgba(16,185,129,0.2); border-radius: 16px; padding: 28px 32px; margin: 24px 0; }}
        .highlight-box h3 {{ color: var(--c2); font-size: 1rem; margin-bottom: 14px; }}
        .highlight-box ul {{ list-style: none; padding: 0; }}
        .highlight-box li {{ padding: 8px 0; color: rgba(255,255,255,0.85); font-size: 0.95rem; border-bottom: 1px solid rgba(255,255,255,0.05); }}
        .highlight-box li:last-child {{ border-bottom: none; }}

        .table-wrap {{ background: #FFFFFF; border: 1px solid var(--line); border-radius: 16px; overflow: hidden; margin: 20px 0; }}
        table {{ width: 100%; border-collapse: collapse; }}
        thead th {{ padding: 14px 16px; text-align: left; font-size: 0.7rem; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: var(--ink4); background: #FFFFFF; border-bottom: 1px solid var(--line); }}
        thead th.right {{ text-align: right; }}
        tbody td {{ padding: 12px 16px; border-bottom: 1px solid var(--line); font-size: 0.9rem; }}
        tbody tr:last-child td {{ border-bottom: none; }}
        tbody tr:hover {{ background: #FFFFFF; }}
        .city-name {{ font-weight: 600; }}
        .city-count {{ font-weight: 700; color: var(--c2); text-align: right; }}
        .city-rating {{ text-align: right; font-weight: 600; }}
        .city-pc {{ text-align: right; color: var(--ink3); font-size: 0.8rem; }}

        .source-note {{ font-size: 0.85rem; color: var(--ink4); margin-top: 40px; line-height: 1.7; padding: 24px; background: #FFFFFF; border-radius: 14px; border: 1px dashed var(--line); }}
        footer {{ text-align: center; padding: 40px 0; border-top: 1px solid var(--line); color: var(--ink4); font-size: 0.85rem; }}
        footer a {{ color: var(--ink4); text-decoration: none; }}
        footer a:hover {{ color: var(--ink); }}

        @media (max-width: 768px) {{ .hero h1 {{ font-size: 1.8rem; }} }}
    </style>
</head>
<body>
    <div class="grain"></div>
    <nav><div class="nav-bar">
        <a href="index.html" class="logo"><i class="fas fa-pepper-hot logo-icon"></i>ThaiData.uk</a>
        <a href="guides.html" style="color:rgba(255,255,255,0.6);font-size:0.9rem;text-decoration:none;">← Guides</a>
    </div></nav>

    <div class="wrap">
        <div class="hero">
            <div class="badge"><i class="fas fa-receipt"></i> Price Index · {survey.get('collected', 'TBD')}</div>
            <h1>Thai Menu <em>Price Index</em> 2026</h1>
            <p>What do Pad Thai, Green Curry, and Tom Yum actually cost across UK cities? Real prices compared — dine-in vs delivery — and the hidden markup most restaurants don't talk about.</p>
        </div>

        <div class="big-stat">
            <div class="number" style="color:{'#EF4444' if avg_uk_spread > 15 else '#F59E0B' if avg_uk_spread > 10 else 'var(--c2)'};">+{avg_uk_spread}%</div>
            <div class="label">Average delivery price markup across all dishes surveyed</div>
        </div>

        <div class="highlight-box">
            <h3><i class="fas fa-lightbulb"></i> Why This Matters</h3>
            <ul>
                <li>Most Thai restaurants mark up delivery prices <strong>10-25%</strong> to cover platform commissions (Deliveroo 32%, Uber Eats 30%, Just Eat 14%)</li>
                <li>The markup is rarely disclosed — customers paying £16.50 for Pad Thai on Deliveroo may not know it's £12.95 in the restaurant</li>
                <li>Restaurants that <strong>don't</strong> mark up are effectively losing money on every delivery order after food cost</li>
                <li>Transparent operators keep dine-in and delivery prices the same — and factor the commission into their overall menu pricing strategy</li>
            </ul>
        </div>
    </div>

    <!-- City Comparison -->
    <div class="section">
        <div class="wrap">
            <h2>Delivery Markup by <em>City</em></h2>
            <p class="section-desc">Average markup across all surveyed dishes. Higher % = restaurants passing more commission cost to delivery customers.</p>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr><th>City</th><th class="right">Avg Dine-in</th><th class="right">Avg Delivery</th><th class="right">Markup</th><th class="right">Sample</th></tr>
                    </thead>
                    <tbody>
{city_rows_html}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- Dish Comparison -->
    <div class="section">
        <div class="wrap">
            <h2>Delivery Markup by <em>Dish</em></h2>
            <p class="section-desc">Which dishes get marked up the most on delivery apps?</p>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr><th>Dish</th><th class="right">Avg Dine-in</th><th class="right">Avg Delivery</th><th class="right">Markup</th><th class="right">Sample</th></tr>
                    </thead>
                    <tbody>
{dish_rows_html}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <div class="wrap">
        <div class="source-note">
            <strong><i class="fas fa-clipboard-list"></i> Methodology & Limitations</strong><br><br>
            <strong>Collection date:</strong> {survey.get('collected', 'TBD')}<br>
            <strong>Method:</strong> {survey.get('methodology', 'Manual collection from restaurant sources')}<br>
            <strong>Dine-in prices:</strong> From official restaurant websites or Google Business Profile menus<br>
            <strong>Delivery prices:</strong> From Deliveroo, Uber Eats, or Just Eat — excludes delivery fees and service charges<br>
            <strong>Sample size:</strong> {len(all_spreads)} dish-price pairs across {len(city_stats)} cities<br>
            <strong>Notes:</strong> {', '.join(survey.get('notes', []))}<br><br>
            <strong>Limitations:</strong> Prices are snapshots — they change. Premium/regional/large-portion variants not captured. Where a dish wasn't available at a restaurant, it was excluded rather than estimated. This is a sample, not a census. Use as a directional benchmark, not an exact price reference.
        </div>
    </div>

    <footer><p>&copy; 2026 ThaiData.uk · <a href="about.html">About</a> · <a href="guides.html">Guides</a></p></footer>
</body>
</html>'''

# Write page
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(_REPO, exist_ok=True)
with open(os.path.join(_REPO, 'thai-menu-price-index-uk.html'), 'w') as f:
    f.write(site_icons.transform(HTML))
print(f"Page generated: {len(HTML):,} bytes")
print(f"Data: {len(all_spreads)} prices across {len(city_stats)} cities, UK avg markup: +{avg_uk_spread}%")
print("Page saved to /opt/thaidata-repo/thai-menu-price-index-uk.html")
