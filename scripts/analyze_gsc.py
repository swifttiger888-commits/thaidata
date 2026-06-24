#!/usr/bin/env python3
"""
Parse a Google Search Console Performance CSV export and produce a readable report.

Usage:
    # First run — just show current data
    python3 scripts/analyze_gsc.py path/to/gsc-export.csv

    # With previous week's export for comparison
    python3 scripts/analyze_gsc.py path/to/current.csv --baseline path/to/previous.csv

Output:
    - Prints to stdout
    - Saves .hermes/plans/gsc-report-<date>.md if GSC_REPORT_DIR is set

Columns expected (auto-detected):
    Queries, Pages, Clicks, Impressions, CTR, Position, Date
"""

import csv
import sys
import os
import re
from datetime import datetime
from collections import defaultdict

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))

def detect_columns(headers):
    """Map header names to canonical column names (case-insensitive, fuzzy)."""
    mapping = {}
    for h in headers:
        h_lower = h.strip().lower()
        if h_lower == 'query' or h_lower == 'queries' or h_lower == 'top queries':
            mapping[h] = 'query'
        elif h_lower == 'page' or h_lower == 'pages' or h_lower == 'landing page':
            mapping[h] = 'page'
        elif h_lower == 'clicks':
            mapping[h] = 'clicks'
        elif h_lower == 'impressions':
            mapping[h] = 'impressions'
        elif h_lower == 'ctr':
            mapping[h] = 'ctr'
        elif h_lower == 'position' or h_lower == 'avg position' or h_lower == 'avg. position':
            mapping[h] = 'position'
        elif h_lower.startswith('date'):
            mapping[h] = 'date'
    return mapping

def parse_value(val, col_type):
    """Parse a cell value into the right type."""
    val = val.strip()
    if not val or val == '-':
        return None
    if col_type in ('clicks', 'impressions'):
        return int(val.replace(',', ''))
    if col_type == 'ctr':
        return float(val.replace('%', '')) / 100.0
    if col_type == 'position':
        return float(val)
    return val

def load_csv(path, label='current'):
    """Load a GSC CSV and return a list of dicts with parsed values."""
    rows = []
    with open(path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        headers = next(reader)
        col_map = detect_columns(headers)
        row_num = 1
        for row in reader:
            row_num += 1
            if not any(cell.strip() for cell in row):
                continue  # skip empty rows
            entry = {}
            for i, h in enumerate(headers):
                if i >= len(row):
                    continue
                canonical = col_map.get(h)
                if canonical:
                    entry[canonical] = parse_value(row[i], canonical)
            # Skip rows with no meaningful data
            if entry.get('clicks') is None and entry.get('impressions') is None:
                continue
            rows.append(entry)
    if not rows:
        print(f"  ERROR: No data rows found in {path}")
        print(f"  Detected columns: {col_map}")
        print(f"  First few rows may have different structure.")
        sys.exit(1)
    return rows

def build_agg(rows):
    """Aggregate by query and by page."""
    by_query = defaultdict(lambda: {'clicks': 0, 'impressions': 0, 'ctr_sum': 0.0, 'position_sum': 0.0, 'count': 0})
    by_page = defaultdict(lambda: {'clicks': 0, 'impressions': 0, 'ctr_sum': 0.0, 'position_sum': 0.0, 'count': 0})

    for r in rows:
        q = r.get('query', '')
        p = r.get('page', '')
        clicks = r.get('clicks') or 0
        impressions = r.get('impressions') or 0
        ctr = r.get('ctr') or 0
        pos = r.get('position') or 10.0

        if q:
            by_query[q]['clicks'] += clicks
            by_query[q]['impressions'] += impressions
            by_query[q]['ctr_sum'] += ctr
            by_query[q]['position_sum'] += pos
            by_query[q]['count'] += 1

        if p:
            by_page[p]['clicks'] += clicks
            by_page[p]['impressions'] += impressions
            by_page[p]['ctr_sum'] += ctr
            by_page[p]['position_sum'] += pos
            by_page[p]['count'] += 1

    def finalize(d):
        return {
            k: {
                'clicks': v['clicks'],
                'impressions': v['impressions'],
                'ctr': v['ctr_sum'] / v['count'] if v['count'] > 0 else 0,
                'position': v['position_sum'] / v['count'] if v['count'] > 0 else 0,
            }
            for k, v in d.items()
        }

    return finalize(by_query), finalize(by_page)

def top_n(d, key, n=15):
    """Return top n items by key (descending)."""
    return sorted(d.items(), key=lambda x: x[1][key], reverse=True)[:n]

def format_pct(v):
    return f"{v*100:.1f}%"

def format_pos(v):
    return f"{v:.1f}"

def build_report(rows, label, baseline=None):
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    dates = sorted(set(r['date'] for r in rows if r.get('date')), reverse=True)
    date_range = f"{dates[-1]} → {dates[0]}" if len(dates) > 1 else dates[0] if dates else "unknown"

    by_query_agg, by_page_agg = build_agg(rows)

    total_clicks = sum(r['clicks'] or 0 for r in rows if r.get('clicks'))
    total_impressions = sum(r['impressions'] or 0 for r in rows if r.get('impressions'))
    avg_ctr = total_clicks / total_impressions * 100 if total_impressions > 0 else 0
    avg_pos = sum(r['position'] or 0 for r in rows if r.get('position')) / max(len([r for r in rows if r.get('position')]), 1)

    lines = []
    lines.append(f"# GSC Report — {label}")
    lines.append(f"_Generated: {now}_")
    lines.append(f"_Date range: {date_range}_")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Clicks | {total_clicks:,} |")
    lines.append(f"| Impressions | {total_impressions:,} |")
    lines.append(f"| CTR | {avg_ctr:.1f}% |")
    lines.append(f"| Avg Position | {avg_pos:.1f} |")
    lines.append(f"| Unique queries | {len(by_query_agg):,} |")
    lines.append(f"| Unique pages | {len(by_page_agg):,} |")
    lines.append("")

    lines.append("## Top Queries by Clicks")
    lines.append("")
    lines.append("| Query | Clicks | Impressions | CTR | Position |")
    lines.append("|-------|--------|-------------|-----|----------|")
    for q, v in top_n(by_query_agg, 'clicks'):
        lines.append(f"| {q} | {v['clicks']:,} | {v['impressions']:,} | {format_pct(v['ctr'])} | {format_pos(v['position'])} |")
    lines.append("")

    lines.append("## Top Queries by Impressions")
    lines.append("")
    lines.append("| Query | Impressions | Clicks | CTR | Position |")
    lines.append("|-------|-------------|--------|-----|----------|")
    for q, v in top_n(by_query_agg, 'impressions'):
        lines.append(f"| {q} | {v['impressions']:,} | {v['clicks']:,} | {format_pct(v['ctr'])} | {format_pos(v['position'])} |")
    lines.append("")

    lines.append("## Top Pages by Clicks")
    lines.append("")
    lines.append("| Page | Clicks | Impressions | CTR | Position |")
    lines.append("|------|--------|-------------|-----|----------|")
    for p, v in top_n(by_page_agg, 'clicks', 10):
        short = p.replace('https://thaidata.uk', '')
        lines.append(f"| {short} | {v['clicks']:,} | {v['impressions']:,} | {format_pct(v['ctr'])} | {format_pos(v['position'])} |")
    lines.append("")

    lines.append("## Low-Hanging Fruit (impressions > 100, position < 30, clicks = 0)")
    lines.append("")
    lhf = {k: v for k, v in by_query_agg.items()
           if v['impressions'] >= 100 and v['clicks'] == 0 and v['position'] <= 30}
    if lhf:
        lines.append("| Query | Impressions | Position | CTR (current) |")
        lines.append("|-------|-------------|----------|---------------|")
        for q, v in sorted(lhf.items(), key=lambda x: x[1]['impressions'], reverse=True)[:15]:
            lines.append(f"| {q} | {v['impressions']:,} | {format_pos(v['position'])} | {format_pct(v['ctr'])} |")
    else:
        lines.append("_None found._")
    lines.append("")

    # Diffs against baseline
    if baseline:
        lines.append("## Changes vs Previous Period")
        lines.append("")
        b_queries, b_pages = baseline

        # Queries gaining impressions
        gainers = []
        for q, v in by_query_agg.items():
            bv = b_queries.get(q)
            if bv and bv['impressions'] > 0:
                delta = v['impressions'] - bv['impressions']
                if delta > 50:
                    gainers.append((q, v, bv, delta))
        gainers.sort(key=lambda x: x[3], reverse=True)
        if gainers:
            lines.append("### Biggest Impression Gainers (+50+)")
            lines.append("")
            lines.append("| Query | Before | After | Δ Impressions | Δ Position |")
            lines.append("|-------|--------|-------|---------------|------------|")
            for q, v, bv, delta in gainers[:10]:
                pos_delta = bv['position'] - v['position']  # negative = improved
                pos_str = f"{format_pos(bv['position'])} → {format_pos(v['position'])}"
                lines.append(f"| {q} | {bv['impressions']:,} | {v['impressions']:,} | +{delta:,} | {pos_str} |")

        # Pages losing impressions
        decliners = []
        for q, v in by_query_agg.items():
            bv = b_queries.get(q)
            if bv and bv['impressions'] > 0:
                delta = bv['impressions'] - v['impressions']
                if delta > 50:
                    decliners.append((q, v, bv, delta))
        decliners.sort(key=lambda x: x[3], reverse=True)
        if decliners:
            lines.append("")
            lines.append("### Biggest Impression Decliners (-50+)")
            lines.append("")
            lines.append("| Query | Before | After | Δ Impressions | Δ Position |")
            lines.append("|-------|--------|-------|---------------|------------|")
            for q, v, bv, delta in decliners[:10]:
                pos_delta = v['position'] - bv['position']
                pos_str = f"{format_pos(bv['position'])} → {format_pos(v['position'])}"
                lines.append(f"| {q} | {bv['impressions']:,} | {v['impressions']:,} | -{delta:,} | {pos_str} |")
        lines.append("")

        # New queries appearing
        new_queries = set(by_query_agg.keys()) - set(b_queries.keys())
        if new_queries:
            new_with_data = {q: by_query_agg[q] for q in new_queries if by_query_agg[q]['impressions'] > 20}
            if new_with_data:
                lines.append("### New Queries Appearing")
                lines.append("")
                lines.append("| Query | Impressions | Clicks | Position |")
                lines.append("|-------|-------------|--------|----------|")
                for q, v in sorted(new_with_data.items(), key=lambda x: x[1]['impressions'], reverse=True)[:10]:
                    lines.append(f"| {q} | {v['impressions']:,} | {v['clicks']:,} | {format_pos(v['position'])} |")
                lines.append("")

        # Queries no longer appearing
        vanished = set(b_queries.keys()) - set(by_query_agg.keys())
        if vanished:
            vanished_with_data = {q: b_queries[q] for q in vanished if b_queries[q]['impressions'] > 20}
            if vanished_with_data:
                lines.append("### Queries No Longer Appearing")
                lines.append("")
                lines.append("| Query | Had Impressions | Had Position |")
                lines.append("|-------|-----------------|--------------|")
                for q, v in sorted(vanished_with_data.items(), key=lambda x: x[1]['impressions'], reverse=True)[:10]:
                    lines.append(f"| {q} | {v['impressions']:,} | {format_pos(v['position'])} |")
                lines.append("")

    return '\n'.join(lines)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/analyze_gsc.py <csv_path> [--baseline <baseline_csv>]")
        sys.exit(1)

    csv_path = sys.argv[1]
    baseline_path = None
    if '--baseline' in sys.argv:
        idx = sys.argv.index('--baseline')
        if idx + 1 < len(sys.argv):
            baseline_path = sys.argv[idx + 1]

    if not os.path.exists(csv_path):
        print(f"ERROR: File not found: {csv_path}")
        sys.exit(1)

    print(f"Loading current data: {csv_path}")
    rows = load_csv(csv_path, 'current')
    print(f"  {len(rows)} data rows loaded")

    baseline = None
    if baseline_path:
        if os.path.exists(baseline_path):
            print(f"Loading baseline data: {baseline_path}")
            b_rows = load_csv(baseline_path, 'baseline')
            print(f"  {len(b_rows)} data rows loaded")
            baseline = build_agg(b_rows)
        else:
            print(f"  Baseline file not found, skipping diff")

    label = os.path.splitext(os.path.basename(csv_path))[0]
    report = build_report(rows, label, baseline)

    print("\n" + "="*60)
    print(report)
    print("="*60)

    # Save to plans dir
    report_dir = os.environ.get('GSC_REPORT_DIR', os.path.join(REPO, '.hermes', 'plans'))
    os.makedirs(report_dir, exist_ok=True)
    today = datetime.now().strftime('%Y-%m-%d')
    out_path = os.path.join(report_dir, f'gsc-report-{today}.md')
    with open(out_path, 'w') as f:
        f.write(report)
    print(f"\nReport saved: {out_path}")

if __name__ == '__main__':
    main()
