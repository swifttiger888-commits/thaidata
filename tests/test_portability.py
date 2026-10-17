"""Portability guard: scripts must not hardcode the production /tmp symlink.

/tmp/thaidata-repo is a symlink to the repo root on the production host but
does not exist on CI runners, which caused two CI failures (May/Oct 2026).
Scripts must resolve the repo root from __file__.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_no_hardcoded_tmp_repo_paths():
    offenders = []
    for p in (ROOT / "scripts").rglob("*.py"):
        text = p.read_text(encoding="utf-8", errors="replace")
        for pattern in ("'/tmp/thaidata-repo", '"/tmp/thaidata-repo'):
            if pattern in text:
                offenders.append(f"{p.relative_to(ROOT)} -> {pattern}")
    assert not offenders, "hardcoded production paths:\n" + "\n".join(offenders)
