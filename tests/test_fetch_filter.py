"""Fetch name-filter tests: allowlist + blocklist behaviour."""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FETCH_PATH = REPO / "scripts" / "fetch_all_thai_data.py"


def _load_module():
    """Import fetch_all_thai_data.py without running main()."""
    src = FETCH_PATH.read_text().replace("def main()", "def _main()")
    mod = types.ModuleType("fetch_mod")
    mod.__file__ = str(FETCH_PATH)
    sys.path.insert(0, str(REPO / "scripts"))
    exec(compile(src, str(FETCH_PATH), "exec"), mod.__dict__)
    return mod


def test_apply_name_filter_allowlist_and_blocklist():
    mod = _load_module()
    ests = [
        {"FHRSID": 1, "BusinessName": "Thai Orchid"},
        {"FHRSID": 2, "BusinessName": "Khop Chai Deu"},
        {"FHRSID": 3, "BusinessName": "Zaal Indian Cuisine"},
        {"FHRSID": 4, "BusinessName": "Zaal Thai Dining"},
    ]
    kept, dropped = mod.apply_name_filter(ests, {2}, {4})
    names = [e["BusinessName"] for e in kept]
    assert "Thai Orchid" in names          # name contains 'thai'
    assert "Khop Chai Deu" in names        # allowlisted without 'thai'
    assert "Zaal Indian Cuisine" not in names  # no 'thai', not allowlisted
    assert "Zaal Thai Dining" not in names     # blocklisted despite 'thai'
    assert dropped == 2


def test_allowlist_file_loads():
    mod = _load_module()
    allowlist, blocklist = mod.load_name_filter_lists()
    assert 1790288 in allowlist
    assert len(blocklist) >= 9
