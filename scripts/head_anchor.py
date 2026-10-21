"""Find the real end of <head> before touching it.

A page whose inline JSON-LD carries a stray '</head>' inside a string used to
have its stylesheet links and .ic rules injected *into the JSON-LD*, where the
browser never applies them — thai-competitor-radar shipped with no working
fonts, no form styles, and a corrupt breadcrumb. The last '</head>' before
<body is always the real one.
"""
from __future__ import annotations


def head_end(text: str) -> int:
    """Index of the closing </head>, or -1."""
    body = text.lower().find('<body')
    limit = body if body > 0 else len(text)
    return text.lower().rfind('</head>', 0, limit)


def in_head(text: str, needle: str) -> bool:
    """True when needle already appears in the head (not in a script body)."""
    end = head_end(text)
    return needle in (text[:end] if end > 0 else text)
