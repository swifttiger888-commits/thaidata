#!/usr/bin/env python3
"""Consistency checks for the auto-generated MCP fallback and HF publish scripts."""
import json
import os
import sys

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(REPO, 'scripts'))

import generate_mcp_fallback as fallback  # noqa: E402
import publish_hf_dataset as publish  # noqa: E402


def test_fallback_matches_repo_data():
    """functions/mcp.js EMBEDDED_DATA must equal a fresh generation (not stale)."""
    js = open(os.path.join(REPO, 'functions', 'mcp.js')).read()
    regenerated = fallback.apply_block(js, fallback.build_block())
    assert regenerated == js, 'EMBEDDED_DATA is stale — run scripts/generate_mcp_fallback.py'


def test_fallback_block_is_generated_and_complete():
    block = fallback.build_block()
    assert 'const EMBEDDED_DATA = {' in block
    assert 'AUTO-GENERATED' in block
    for city in fallback.FALLBACK_CITIES:
        assert f'name: "{city}"' in block
    assert 'total_uk_thai_businesses' in block


def test_hf_render_matches_source_counts():
    files = publish.render_files()
    rest = json.load(open(os.path.join(REPO, 'data', 'restaurants.json')))['restaurants']
    cities = json.load(open(os.path.join(REPO, 'api', 'v1', 'cities.json')))['cities']
    assert files['restaurants.jsonl'].count('\n') == len(rest)
    assert files['cities.jsonl'].count('\n') == len(cities)
    assert '{{' not in files['README.md'], 'unrendered placeholder left in README'


def test_local_blob_shas_stable():
    shas = publish.local_blob_shas({'a.txt': 'hello\n'})
    assert len(shas['a.txt']) == 40
    # same content → same sha; different content → different sha
    assert shas['a.txt'] == publish.local_blob_shas({'a.txt': 'hello\n'})['a.txt']
    assert shas['a.txt'] != publish.local_blob_shas({'a.txt': 'bye\n'})['a.txt']
