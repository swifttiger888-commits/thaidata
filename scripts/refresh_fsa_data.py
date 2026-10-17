#!/usr/bin/env python3
"""
Weekly FSA data refresh for ThaiData.uk
Pulls fresh data, detects changes, rebuilds affected pages, pushes to git.
Designed to run as a cron job or manually.
"""
import json, time, os, subprocess
from datetime import datetime

from fsa_client import fetch_all, count_by_la

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = '/tmp/thai_fsa_latest.json'
CHANGE_LOG = '/tmp/thai_fsa_changes.txt'

def main() -> None:
    changes = []
    start = datetime.now()
    print(f"=== ThaiData FSA Refresh — {start.strftime('%Y-%m-%d %H:%M')} ===\n")
    
    # 1. Pull fresh data
    print("Fetching FSA data...")
    all_ests = []
    
    # Core Thai search (FHRS + FHIS)
    for scheme in ['FHRS', 'FHIS']:
        for bt in ['1', '7844']:
            label = f"{scheme} {'Restaurant' if bt == '1' else 'Takeaway'}"
            ests = fetch_all('Thai', bt, scheme)
            print(f"  {label}: {len(ests)}")
            all_ests.extend(ests)
    
    # Deduplicate
    seen = {}
    for e in all_ests:
        fid = e['FHRSID']
        if fid not in seen:
            seen[fid] = e
    all_ests = list(seen.values())
    print(f"  Deduped: {len(all_ests)}")
    
    # Missing chains (with delay to avoid rate limits)
    CHAINS = ['Giggling Squid', 'Busaba', 'Chaophraya', 'Patara', 'Sukhothai', 'Zaap']
    chain_added = 0
    for chain in CHAINS:
        for scheme in ['FHRS', 'FHIS']:
            for bt in ['1', '7844']:
                time.sleep(0.5)
                try:
                    ests = fetch_all(chain, bt, scheme)
                    for e in ests:
                        fid = e['FHRSID']
                        if fid not in seen:
                            seen[fid] = e
                            all_ests.append(e)
                            chain_added += 1
                except Exception as _e:
                    pass
    print(f"  Chain additions: {chain_added}")
    
    total = len(all_ests)
    print(f"  TOTAL: {total}")
    
    # 2. Count by LA
    new_by_la = count_by_la(all_ests)
    
    # 3. Compare with previous
    old_data = {}
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            old_data = json.load(f)
    
    old_total = old_data.get('total', 0)
    old_by_la = old_data.get('by_la', {})
    
    if old_total > 0:
        diff = total - old_total
        changes.append(f"Total change: {diff:+d} (was {old_total}, now {total})")
        
        # City-level changes
        big_changes = []
        for la in set(list(new_by_la.keys()) + list(old_by_la.keys())):
            old_count = old_by_la.get(la, {}).get('total', 0)
            new_count = new_by_la.get(la, {}).get('total', 0)
            delta = new_count - old_count
            if abs(delta) >= 3:
                big_changes.append((la, old_count, new_count, delta))
        
        if big_changes:
            changes.append(f"\nSignificant city changes (≥3):")
            for la, old, new, delta in sorted(big_changes, key=lambda x: abs(x[3]), reverse=True):
                changes.append(f"  {la}: {old} → {new} ({delta:+d})")
        
        # New cities with Thai restaurants
        new_cities = set(new_by_la.keys()) - set(old_by_la.keys())
        new_with_data = [c for c in new_cities if new_by_la[c]['total'] > 0]
        if new_with_data:
            changes.append(f"\nNew cities with Thai businesses: {len(new_with_data)}")
            for c in sorted(new_with_data, key=lambda x: new_by_la[x]['total'], reverse=True)[:5]:
                changes.append(f"  {c}: {new_by_la[c]['total']}")
    else:
        changes.append("First run — no comparison available")
    
    # 4. Save new data
    with open(DATA_FILE, 'w') as f:
        json.dump({
            'total': total,
            'by_la': {la: dict(counts) for la, counts in new_by_la.items()},
            'date': start.strftime('%Y-%m-%d %H:%M'),
            'chain_added': chain_added
        }, f, indent=2)
    
    # 5. Write change log
    with open(CHANGE_LOG, 'w') as f:
        f.write(f"ThaiData FSA Refresh — {start.strftime('%Y-%m-%d %H:%M')}\n")
        f.write("=" * 50 + "\n")
        for line in changes:
            f.write(line + "\n")
    
    # 6. If there are significant changes, rebuild and push
    significant = (abs(total - old_total) >= 5) if old_total > 0 else True
    
    if significant and old_total > 0:
        print(f"\n🔄 Significant changes detected. Rebuilding pages and pushing...")
        
        # Push the updated data files
        os.chdir(REPO_DIR)

        # Guard: abort if unrelated files are dirty or staged
        status = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
        owned = {'data/restaurants.json', 'api/v1/cities.json', 'api/v1/data.json'}
        dirty = [line.split()[-1] for line in status.stdout.split('\n') if line.strip() and line.split()[-1] not in owned]
        if dirty:
            print(f"   ⚠️ Aborting push: {len(dirty)} unrelated file(s) dirty/staged")
            for f in dirty[:10]:
                print(f"      {f}")
            return

        # Stage only the data files the pipeline owns
        subprocess.run(['git', 'add', 'data/restaurants.json', 'api/v1/cities.json', 'api/v1/data.json'],
                       capture_output=True)

        diff = total - old_total
        commit_msg = f"Auto-refresh: FSA data update — {total} Thai businesses ({diff:+d})"
        result = subprocess.run(['git', 'commit', '-m', commit_msg], capture_output=True, text=True)
        if result.returncode != 0:
            print("   ℹ️ No changes to commit (data unchanged)")
            return

        # Pull + push — fail loudly on non-zero
        pull = subprocess.run(['git', 'pull', '--rebase'], capture_output=True, text=True)
        if pull.returncode != 0:
            print(f"   ❌ git pull --rebase failed:\n{pull.stderr}")
            # Attempt abort to leave repo clean
            subprocess.run(['git', 'rebase', '--abort'], capture_output=True)
            return

        push = subprocess.run(['git', 'push'], capture_output=True, text=True)
        if push.returncode != 0:
            print(f"   ❌ git push failed:\n{push.stderr}")
            return

        print("   ✅ Pushed to GitHub — Cloudflare will auto-deploy")
        # WebSub ping — notify subscribers (Google, AI crawlers) of updated content
        print("   📡 Pinging WebSub hub...")
        subprocess.run(['python3', f'{REPO_DIR}/scripts/websub-ping.py'], capture_output=False)
    elif old_total > 0:
        print(f"\n✅ No significant changes ({total - old_total:+d}). Skipping rebuild.")
    else:
        print(f"\n📊 First run complete. {total} businesses recorded as baseline.")
    
    print(f"\nDone in {(datetime.now() - start).total_seconds():.1f}s")
    print(f"Change log: {CHANGE_LOG}")
    
    # Print summary for cron output
    print("\n" + "\n".join(changes))

if __name__ == "__main__":
    main()
