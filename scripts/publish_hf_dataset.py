#!/usr/bin/env python3
"""Publish the current ThaiData snapshot to HuggingFace.

Repo: swifttiger/uk-thai-restaurants (public dataset, ODbL licence).
Rebuilds restaurants.jsonl + cities.jsonl + README.md from repo data and
uploads via the `hf` CLI — but only when content actually changed (compares
git blob SHAs against the remote tree, so identical uploads never create
empty revisions).

Safety rails:
- No-op when unchanged.
- Disable entirely with env SKIP_HF_PUBLISH=1 or by creating a file named
  `.no_hf_publish` at the repo root.

Run weekly as the final step of fsa_pipeline.py.
"""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
HF_REPO = 'swifttiger/uk-thai-restaurants'
TEMPLATE = os.path.join(REPO, 'scripts', 'hf_dataset_readme_template.md')
REST_FILE = os.path.join(REPO, 'data', 'restaurants.json')
CITIES_FILE = os.path.join(REPO, 'api', 'v1', 'cities.json')


def render_files() -> dict[str, str]:
    """Build the three dataset files from current repo data."""
    rest = json.load(open(REST_FILE))
    cities = json.load(open(CITIES_FILE))
    rows = rest['restaurants']
    n_rest = len(rows)
    n_city = len(cities['cities'])
    geo = sum(1 for r in rows if r.get('latitude') is not None)
    ungeocoded = round(100 * (n_rest - geo) / n_rest) if n_rest else 0
    updated = dt.datetime.strptime(rest.get('updated', '2026-01-01'), '%Y-%m-%d')
    last_updated = f'{updated.day} {updated.strftime("%B")} {updated.year}'

    template = open(TEMPLATE).read()
    readme = (
        template
        .replace('{{REST_COUNT}}', f'{n_rest:,}')
        .replace('{{CITY_COUNT}}', str(n_city))
        .replace('{{LAST_UPDATED}}', last_updated)
        .replace('{{UNGEOCODED_PCT}}', str(ungeocoded))
    )
    return {
        'restaurants.jsonl': ''.join(json.dumps(r) + '\n' for r in rows),
        'cities.jsonl': ''.join(json.dumps(c) + '\n' for c in cities['cities']),
        'README.md': readme,
    }


def local_blob_shas(files: dict[str, str]) -> dict[str, str]:
    """Git-style blob SHA for each file's exact bytes (no writes needed)."""
    shas = {}
    for name, content in files.items():
        res = subprocess.run(['git', 'hash-object', '--stdin'],
                             input=content.encode(), capture_output=True)
        shas[name] = res.stdout.decode().strip()
    return shas


def remote_blob_shas() -> dict[str, str] | None:
    """Blob SHAs from the remote HF dataset tree; None if unreachable."""
    url = f'https://huggingface.co/api/datasets/{HF_REPO}/tree/main'
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            tree = json.load(r)
        return {t['path']: t['oid'] for t in tree if t.get('type') == 'file'}
    except Exception as e:
        print(f'⚠️  could not read remote tree ({e}) — will attempt upload')
        return None


def hf_cli() -> str:
    found = shutil.which('hf') or os.path.expanduser('~/.local/bin/hf')
    if not os.path.isfile(found):
        raise SystemExit('hf CLI not found (install huggingface_hub[cli])')
    return found


def main() -> None:
    if os.environ.get('SKIP_HF_PUBLISH') or os.path.exists(os.path.join(REPO, '.no_hf_publish')):
        print('HF publish disabled (SKIP_HF_PUBLISH / .no_hf_publish) — skipping')
        return

    files = render_files()
    local = local_blob_shas(files)
    remote = remote_blob_shas()
    if remote is not None and all(remote.get(k) == v for k, v in local.items()):
        print('HF dataset already current — skipping upload')
        return

    with tempfile.TemporaryDirectory(prefix='hf-publish-') as tmp:
        for name, content in files.items():
            with open(os.path.join(tmp, name), 'w') as f:
                f.write(content)
        n_rest = files['restaurants.jsonl'].count('\n')
        n_city = files['cities.jsonl'].count('\n')
        msg = f'Refresh: {n_rest:,} businesses / {n_city} cities'
        res = subprocess.run(
            [hf_cli(), 'upload', HF_REPO, tmp, '--type', 'dataset',
             '--commit-message', msg],
            capture_output=True, text=True)
        out = (res.stdout or '') + (res.stderr or '')
        if res.returncode != 0:
            print('❌ hf upload failed:\n' + out[-800:])
            sys.exit(1)
        url = next((l.split('url=', 1)[1] for l in out.splitlines() if 'url=' in l), '')
        print(f'✅ HF dataset updated: {msg}' + (f'\n   {url}' if url else ''))


if __name__ == '__main__':
    main()
