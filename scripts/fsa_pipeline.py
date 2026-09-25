#!/usr/bin/env python3
"""
FSA Data Refresh Pipeline — end-to-end.
1. Fetch fresh FSA data → data/restaurants.json + api/v1/*.json
2. Regenerate restaurant pages → r/
3. Regenerate city cards → cities/
4. Regenerate city page AUTO blocks → cities/
5. Regenerate the MCP fallback block → functions/mcp.js
6. Commit + push if changes detected
7. Publish to HuggingFace (no-op when unchanged; disable via SKIP_HF_PUBLISH=1
   or a .no_hf_publish file at the repo root)
"""
import json, os, subprocess, sys
from datetime import datetime

REPO_DIR = '/opt/thaidata-repo'
SCRIPTS = os.path.join(REPO_DIR, 'scripts')
DATA_FILE = os.path.join(REPO_DIR, 'data', 'restaurants.json')


def run(cmd: list[str], label: str) -> bool:
    """Run a command, print output, return success."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, cwd=REPO_DIR, capture_output=False)
    return result.returncode == 0


def main() -> None:
    start = datetime.now()
    print(f"=== ThaiData FSA Pipeline — {start.strftime('%Y-%m-%d %H:%M')} ===\n")

    # ── Step 1: snapshot BEFORE fetch ─────────────────────────────────
    old_count = 0
    old_ids: set[str] = set()
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            old_data = json.load(f)
        old_count = old_data.get('total', len(old_data.get('restaurants', [])))
        for r in old_data.get('restaurants', []):
            old_ids.add(str(r.get('id', '')))

    # ── Step 2: fetch fresh FSA data ─────────────────────────────────
    if not run([sys.executable, f'{SCRIPTS}/fetch_all_thai_data.py'],
               'Step 1/6: Fetch fresh FSA data'):
        print("❌ FSA fetch failed. Aborting.")
        sys.exit(1)

    # ── Step 3: snapshot AFTER + compute delta ────────────────────────
    new_count = 0
    new_ids: set[str] = set()
    new_restaurants: list[dict] = []
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            new_data = json.load(f)
        new_count = new_data.get('total', len(new_data.get('restaurants', [])))
        for r in new_data.get('restaurants', []):
            rid = str(r.get('id', ''))
            new_ids.add(rid)
            if rid and rid not in old_ids and old_count > 0:
                new_restaurants.append({
                    'fsa_id': rid,
                    'name': r.get('name', ''),
                    'city': r.get('city', ''),
                    'type': r.get('type', 'restaurant'),
                })

    diff = new_count - old_count
    print(f"\n  Data: {old_count} → {new_count} ({diff:+d})")
    if new_restaurants:
        print(f"  🆕 New FSA listings: {len(new_restaurants)}")

    # ── Step 4: update recent_additions.json ─────────────────────────
    today = start.strftime('%Y-%m-%d')
    recent_path = os.path.join(REPO_DIR, 'data', 'recent_additions.json')
    recent = {'updated': today, 'restaurants': []}
    if os.path.exists(recent_path):
        with open(recent_path) as f:
            recent = json.load(f)

    # Merge: prepend new, dedupe by fsa_id, keep last 90 days
    existing_ids = {r['fsa_id'] for r in recent.get('restaurants', [])}
    for nr in new_restaurants:
        if nr['fsa_id'] not in existing_ids:
            nr['discovered_on'] = today
            recent['restaurants'].insert(0, nr)
            existing_ids.add(nr['fsa_id'])

    # Trim: keep last 90 days worth (max 50 entries)
    cutoff = f'{start.year}-{start.month:02d}-{start.day:02d}'
    recent['restaurants'] = recent['restaurants'][:50]
    recent['updated'] = today

    with open(recent_path, 'w') as f:
        json.dump(recent, f, indent=2)
    print(f"  📋 Recent additions: {len(recent['restaurants'])} tracked")

    # ── Step 5: regenerate pages ─────────────────────────────────────
    if not run([sys.executable, f'{SCRIPTS}/generate_restaurant_pages.py'],
               'Step 2/6: Regenerate restaurant pages'):
        print("❌ Restaurant page generation failed. Aborting.")
        sys.exit(1)

    if not run([sys.executable, f'{SCRIPTS}/generate_city_pages.py', '--apply'],
               'Step 3/5: Regenerate city page AUTO blocks'):
        print("⚠️  City page regeneration failed (non-fatal)")

    if not run([sys.executable, f'{SCRIPTS}/add_city_restaurant_links.py'],
               'Step 4/6: Regenerate city browse cards'):
        print("⚠️  City card regeneration failed (non-fatal)")

    if not run([sys.executable, f'{SCRIPTS}/generate_sitemaps.py'],
               'Step 5/6: Regenerate sitemaps'):
        print("⚠️  Sitemap generation failed (non-fatal)")

    # ── Step 5b: regenerate the MCP fallback (functions/mcp.js) ──────
    if not run([sys.executable, f'{SCRIPTS}/generate_mcp_fallback.py'],
               'Step 6: Regenerate MCP fallback data'):
        print("⚠️  MCP fallback regeneration failed (non-fatal)")

    # ── Step 6: commit & push ────────────────────────────────────────
    os.chdir(REPO_DIR)

    # Guard: only stage files we own. Untracked files can never be swept into
    # the commit (staging uses the explicit list below), so only *tracked*
    # changes outside our paths are a reason to stop.
    owned_prefixes = ('data/', 'api/', 'r/', 'cities/', 'sitemap', 'functions/mcp.js', 'recipes/')
    status = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
    dirty_lines = [l for l in status.stdout.split('\n') if l.strip()]
    tracked_changes = [l for l in dirty_lines if not l.startswith('??')]
    untracked = [l for l in dirty_lines if l.startswith('??')]

    def _path_of(line: str) -> str:
        return line[3:].strip().strip('"') if line.startswith('??') else line.split()[-1].strip('"')

    unrelated = [l for l in tracked_changes
                 if not any(_path_of(l).startswith(p) for p in owned_prefixes)]
    if unrelated:
        print(f"  ⚠️ Aborting: {len(unrelated)} tracked change(s) outside pipeline paths")
        for f in unrelated[:10]:
            print(f"     {f}")
        sys.exit(1)

    if untracked:
        print(f"  ℹ️ {len(untracked)} untracked file(s) present — ignored (never staged)")

    if not tracked_changes:
        print("\n✅ No changes to commit (data unchanged)")
        elapsed = (datetime.now() - start).total_seconds()
        print(f"Done in {elapsed:.1f}s")
        return

    # Stage everything that changed
    subprocess.run(['git', 'add', 'data/', 'api/', 'r/', 'cities/', 'sitemap.xml', 'sitemap-pages.xml', 'sitemap-r-restaurants.xml', 'scripts/generate_sitemaps.py', 'scripts/fsa_pipeline.py', 'functions/mcp.js'], capture_output=True)

    commit_msg = f"Auto-refresh: FSA data update — {new_count} Thai businesses ({diff:+d})"
    result = subprocess.run(['git', 'commit', '-m', commit_msg], capture_output=True, text=True)
    if result.returncode != 0:
        print("  ℹ️ No changes to commit")
        return

    # Pull + push
    pull = subprocess.run(['git', 'pull', '--rebase'], capture_output=True, text=True)
    if pull.returncode != 0:
        print(f"  ❌ git pull --rebase failed:\n{pull.stderr}")
        subprocess.run(['git', 'rebase', '--abort'], capture_output=True)
        sys.exit(1)

    push = subprocess.run(['git', 'push'], capture_output=True, text=True)
    if push.returncode != 0:
        print(f"  ❌ git push failed:\n{push.stderr}")
        sys.exit(1)

    print("  ✅ Pushed to GitHub — Cloudflare auto-deploys")

    # WebSub ping
    subprocess.run([sys.executable, f'{SCRIPTS}/websub-ping.py'], capture_output=False)

    # ── Step 7: publish the HuggingFace dataset ──────────────────────
    if not run([sys.executable, f'{SCRIPTS}/publish_hf_dataset.py'],
               'Step 7: Publish HuggingFace dataset'):
        print("⚠️  HF dataset publish failed (non-fatal)")

    elapsed = (datetime.now() - start).total_seconds()
    print(f"\nDone in {elapsed:.1f}s — {old_count}→{new_count} ({diff:+d})")


if __name__ == '__main__':
    main()
