"""Menu recipe render guard (Step-0 hotfix, Oct 2026).

Why this file exists: the alias matcher folds protein/dietary variants into one
recipe, so a vegetarian item could render the pork version's photo (and similar
swaps). The guard decides image vs link vs nothing per item. These tests pin:

  - diet detection (flag, name markers, category headings),
  - the render matrix for the real audited items,
  - guard-data integrity (denylist keys, allowlist photos),
  - the built pages themselves (block-level state assertions).
"""
import json
import os
import re
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

import build_menu_page as bmp  # noqa: E402

MENUS = {}


def menu(fsa):
    if fsa not in MENUS:
        for f in os.listdir(os.path.join(REPO, "data", "menus")):
            d = json.load(open(os.path.join(REPO, "data", "menus", f), encoding="utf-8"))
            MENUS[str(d.get("fsa_id"))] = d
    return MENUS[str(fsa)]


def item(fsa, name_sub):
    d = menu(fsa)
    for cat, arr in (d.get("categories") or {}).items():
        if not isinstance(arr, list):
            continue
        for it in arr:
            if isinstance(it, dict) and name_sub.lower() in (it.get("name") or "").lower():
                return it, cat
    raise AssertionError(f"item not found: {name_sub}")


# --- unit: diet detection ---------------------------------------------------

@pytest.mark.parametrize("name,cat,flag,want", [
    ("Vegetable Spring Rolls", "Starters", False, True),
    ("Veg Spring Rolls", "Starters", False, True),
    ("Spring Rolls (veg-6pcs)", "Starters", False, True),
    ("TOFU PAD KHING (V) (S/G/Se/*)", "Stir Fries", False, True),
    ("Deep Fried Tofu Satay (GF, Ve, N)", "Starters", False, True),
    ("Pad Kee Mao", "Vegan", False, True),
    ("Quorn Green Curry", "Vegetarian - Main Dishes", False, True),
    ("Green Curry", "Curries", True, True),
    ("Pork with Ginger", "Pork Dishes", False, False),
    ("Chicken with Ginger", "Chicken Dishes", False, False),
    ("Egg Fried Rice", "Rice", False, False),
])
def test_diet_detection(name, cat, flag, want):
    it = {"name": name, "vegetarian": flag}
    assert bmp._is_diet_item(it, name, cat) is want


# --- unit: render matrix for real audited items -----------------------------

@pytest.mark.parametrize("fsa,name_sub,want_slug,want_mode", [
    # Tier 1: dietary violations -> nothing at all
    ("1966538", "Vegetable Spring Rolls", None, "none"),
    ("1966538", "Street Style Special Egg Fried Rice", "khao-pad", "link"),
    ("537906", "TOFU PAD KHING", None, "none"),
    ("537906", "EGG FRIED RICE", "khao-pad", "link"),
    # Tier 2: protein swap -> link only
    ("372004", "Pork with Ginger", "pad-khing", "link"),
    ("372004", "Chicken with Ginger", "pad-khing", "image"),
    # Cleared positives keep their image
    ("372004", "Green Chicken Curry", "green-curry", "image"),
    ("1966538", "Sweet & Spicy Pork Ribs", "sie-krong-moo-op", "image"),
    # Plant-safe allowlist: veg item on a verified plant photo keeps its image
    ("330059", "Deep-Fried Tofu (V, N)", "tao-hoo-tod", "image"),
    # Plant-safe NOT on allowlist -> suppressed
    ("1931734", "Crispy Mushroom Laab (Ve, gluten*)", None, "none"),
])
def test_render_matrix(fsa, name_sub, want_slug, want_mode):
    it, cat = item(fsa, name_sub)
    slug, mode = bmp.recipe_render_for(it, fsa_id=str(fsa), category=cat)
    assert (slug, mode) == (want_slug, want_mode), f"{name_sub}: got {(slug, mode)}"


# --- guard data integrity ---------------------------------------------------

def test_denylist_fsa_ids_exist():
    guard = json.load(open(os.path.join(REPO, "data", "menu_recipe_guard.json"), encoding="utf-8"))
    known = set()
    for f in os.listdir(os.path.join(REPO, "data", "menus")):
        d = json.load(open(os.path.join(REPO, "data", "menus", f), encoding="utf-8"))
        known.add(str(d.get("fsa_id")))
    for fsa in guard["denylist"]:
        assert fsa in known, f"denylist references unknown fsa_id {fsa}"


def test_plant_safe_slugs_have_photos():
    guard = json.load(open(os.path.join(REPO, "data", "menu_recipe_guard.json"), encoding="utf-8"))
    for slug in guard["plant_safe_slugs"]:
        p = os.path.join(REPO, "recipes", slug, slug + ".jpg")
        assert os.path.isfile(p), f"plant-safe slug has no photo: {slug}"


# --- built pages: block-level state -----------------------------------------

LI_RE = re.compile(r'<li class="dish">(.*?)</li>', re.S)
LABEL_RE = re.compile(
    r'<span class="dish-label">(?:<span class="dish-num">[^<]*</span>\s*)?([^<]*)</span>')
TAG_RE = re.compile(r'<[^>]+>')
import html as _html  # noqa: E402
import unicodedata  # noqa: E402


def _clean_name(s):
    s = unicodedata.normalize("NFKC", _html.unescape(s or ""))
    return re.sub(r"\s+", " ", s).strip().rstrip(".").lower()


def dish_entries(page_path):
    """[(name, state)] for each dish block; name taken from the dish-label span
    (badges and price live outside it, so the name is exact)."""
    txt = open(page_path, encoding="utf-8").read()
    out = []
    for m in LI_RE.finditer(txt):
        body = m.group(1)
        lm = LABEL_RE.search(body)
        if not lm:
            continue
        state = "image" if '<img src="/recipes/' in body else (
            "link" if 'class="recipe-link' in body else "none")
        out.append((_clean_name(lm.group(1)), state))
    return out


def expected_state(it, cat, fsa):
    nslug, mode = bmp.recipe_render_for(it, fsa_id=fsa, category=cat)
    if nslug and mode == "image":
        ok = os.path.isfile(os.path.join(REPO, "recipes", nslug, nslug + ".jpg"))
        return "image" if ok else "link"
    if nslug and mode == "link":
        return "link"
    return "none"


def test_every_rendered_block_matches_the_guard():
    """Site-wide: for every venue page, each rendered dish block's state (image /
    link / none) must equal what the guard computes from the menu JSON — instance
    by instance, including same-named dishes in different categories."""
    problems = []
    for f in sorted(os.listdir(os.path.join(REPO, "data", "menus"))):
        d = json.load(open(os.path.join(REPO, "data", "menus", f), encoding="utf-8"))
        city = re.sub(r"[^a-z0-9]+", "-", d["city"].lower()).strip("-")
        page = None
        for form in {re.sub(r"[^a-z0-9]+", "-", d["restaurant"].lower()).strip("-"),
                     re.sub(r"[^a-z0-9]+", "-", d["restaurant"].lower().replace("'", "")).strip("-")}:
            cand = os.path.join(REPO, "r", city, form, "menu", "index.html")
            if os.path.isfile(cand):
                page = cand
                break
        if page is None:
            continue  # no published page for this menu json
        fsa = str(d.get("fsa_id"))
        entries = dish_entries(page)
        want = {}
        for cat, arr in (d.get("categories") or {}).items():
            if not isinstance(arr, list):
                continue
            for it in arr:
                if isinstance(it, dict) and it.get("name"):
                    want.setdefault(_clean_name(it["name"]), []).append(expected_state(it, cat, fsa))
        got = {}
        for name, state in entries:
            got.setdefault(name, []).append(state)
        for name, exp in want.items():
            act = got.get(name)
            if act is None:
                problems.append((f, name, "missing from page", exp))
            elif sorted(exp) != sorted(act):
                problems.append((f, name, "state mismatch", exp, act))
    assert not problems, f"rendered blocks diverge from the guard: {problems[:12]}"


@pytest.mark.parametrize("page,item_sub,want", [
    ("cornwall/talay-thai", "Vegetable Spring Rolls", "none"),
    ("cornwall/talay-thai", "Street Style Special Egg Fried Rice", "link"),
    ("cornwall/talay-thai", "Sweet & Spicy Pork Ribs", "image"),
    ("north-norfolk/bann-thai-restaurant", "Pork with Ginger", "link"),
    ("north-norfolk/bann-thai-restaurant", "Chicken with Ginger", "image"),
    ("sefton/thai-rice", "TOFU PAD KHING", "none"),
    ("lincoln/araya-thai-restaurant", "Vegetable Spring Roll", "none"),
    ("lincoln/araya-thai-restaurant", "Deep-Fried Tofu", "image"),
    ("warrington/thai-paragon", "PAD KING SOT", "none"),
    ("york/bamboo-thai", "Egg fried rice (V)", "none"),
])
def test_built_pages(page, item_sub, want):
    p = os.path.join(REPO, "r", page, "menu", "index.html")
    assert os.path.isfile(p), f"missing built page: {p}"
    hits = [st for name, st in dish_entries(p) if item_sub.lower() in name]
    assert hits, f"{page}: no block matched {item_sub!r}"
    if want == "none":
        # every matched block must be suppressed (the dish may appear in several
        # categories; want 'none' means the flagged instances are gone)
        assert all(st == "none" for st in hits), f"{page} :: {item_sub!r}: {hits}"
    else:
        assert want in hits, f"{page} :: {item_sub!r}: want {want} among {hits}"
