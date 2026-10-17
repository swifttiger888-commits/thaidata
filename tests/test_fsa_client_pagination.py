"""fsa_client.fetch_all pagination + retry tests (mocked network)."""
from __future__ import annotations

import json
import sys
import types
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))


def _load():
    import importlib.util
    spec = importlib.util.spec_from_file_location("fsa_client_mod", REPO / "scripts" / "fsa_client.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeResp:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def page_payload(rows, total_count, total_pages, page_number=1, page_size=500, returncode="OK"):
    return {
        "establishments": rows,
        "meta": {
            "returncode": returncode,
            "totalCount": total_count,
            "totalPages": total_pages,
            "pageSize": page_size,
            "pageNumber": page_number,
        },
    }


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)


def test_retries_then_succeeds(monkeypatch):
    mod = _load()
    calls = {"n": 0}

    def fake_urlopen(req, timeout=30):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("timed out")
        return FakeResp(page_payload([{"FHRSID": 1, "BusinessName": "Thai One"}], 1, 1))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    out = mod.fetch_all("Thai", "1", "FHRS")
    assert [e["FHRSID"] for e in out] == [1]
    assert calls["n"] == 2, "one retry after the failure"


def test_all_attempts_fail_raises(monkeypatch):
    mod = _load()

    def fake_urlopen(req, timeout=30):
        raise ConnectionError("down")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="failed after 4 attempts"):
        mod.fetch_all("Thai", "1", "FHRS")


def test_paginates_by_total_pages(monkeypatch):
    mod = _load()
    pages = {
        1: page_payload([{"FHRSID": 1}, {"FHRSID": 2}], 5, 3, 1),
        2: page_payload([{"FHRSID": 3}, {"FHRSID": 4}], 5, 3, 2),
        3: page_payload([{"FHRSID": 5}], 5, 3, 3),
    }
    seen = []

    def fake_urlopen(req, timeout=30):
        url = req.full_url
        n = int(url.split("pageNumber=")[1].split("&")[0])
        seen.append(n)
        return FakeResp(pages[n])

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    out = mod.fetch_all("Thai", "1", "FHRS")
    assert [e["FHRSID"] for e in out] == [1, 2, 3, 4, 5]
    assert seen == [1, 2, 3]


def test_empty_page_before_end_raises(monkeypatch):
    mod = _load()
    pages = {
        1: page_payload([{"FHRSID": 1}], 3, 3, 1),
        2: page_payload([], 3, 3, 2),
    }

    def fake_urlopen(req, timeout=30):
        n = int(req.full_url.split("pageNumber=")[1].split("&")[0])
        return FakeResp(pages[n])

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="refusing to publish partial data"):
        mod.fetch_all("Thai", "1", "FHRS")


def test_material_totalcount_shortfall_raises(monkeypatch):
    mod = _load()

    def fake_urlopen(req, timeout=30):
        return FakeResp(page_payload([{"FHRSID": 1}], 100, 1))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="pagination incomplete"):
        mod.fetch_all("Thai", "1", "FHRS")


def test_small_drift_tolerated(monkeypatch):
    mod = _load()

    def fake_urlopen(req, timeout=30):
        return FakeResp(page_payload([{"FHRSID": 1}, {"FHRSID": 2}], 4, 1))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    out = mod.fetch_all("Thai", "1", "FHRS")
    assert len(out) == 2


def test_duplicate_fhrsid_deduped(monkeypatch):
    mod = _load()

    def fake_urlopen(req, timeout=30):
        return FakeResp(page_payload(
            [{"FHRSID": 7, "BusinessName": "A"}, {"FHRSID": 7, "BusinessName": "A again"}], 2, 1))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    out = mod.fetch_all("Thai", "1", "FHRS")
    assert len(out) == 1
