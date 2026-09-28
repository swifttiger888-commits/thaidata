#!/usr/bin/env python3
"""
Sitemap generator for thaidata.uk

Generates:
  - sitemap-r-restaurants.xml  (restaurant detail pages)
  - sitemap-pages.xml           (city pages, static pages, blog posts, tools, chains, learn)
  - sitemap.xml                 (sitemap index)

Discovers restaurant pages from r/*/*/index.html files on disk.
Discovers city pages from cities/*.html files.
Uses curated lists for static/blog/tool/chain/learn pages.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
TODAY = datetime.utcnow().strftime("%Y-%m-%d")


def register_namespace():
    """Register sitemap namespace so output isn't ns0: prefixed."""
    try:
        from xml.etree.ElementTree import register_namespace
        register_namespace("", NS)
    except AttributeError:
        pass


def url_element(loc: str, lastmod: str | None = None, changefreq: str | None = None,
                priority: str | None = None) -> Element:
    """Create a <url> element."""
    el = Element("url")
    loc_el = SubElement(el, "loc")
    loc_el.text = loc
    if lastmod:
        lm = SubElement(el, "lastmod")
        lm.text = lastmod
    if changefreq:
        cf = SubElement(el, "changefreq")
        cf.text = changefreq
    if priority:
        pr = SubElement(el, "priority")
        pr.text = priority
    return el


def discover_restaurant_pages() -> list[dict]:
    """Walk r/<city>/<slug>/index.html and return list of URL dicts.

    Only pages that are actually indexable are submitted:
    - canonical must be self-referencing (skips alternate/duplicate pages)
    - embedded fsa-id must exist in the current restaurants.json (skips stale
      pages whose records were removed)
    - must not be noindex (closed venues, moderation exclusions)
    """
    r_dir = os.path.join(REPO_DIR, "r")
    pages = []
    if not os.path.isdir(r_dir):
        return pages

    # Current fsa ids (single source of truth)
    data_path = os.path.join(REPO_DIR, "data", "restaurants.json")
    current_ids: set[str] = set()
    if os.path.isfile(data_path):
        with open(data_path, encoding="utf-8") as f:
            data = json.load(f)
        current_ids = {str(r["id"]) for r in data.get("restaurants", [])}

    for city in sorted(os.listdir(r_dir)):
        city_path = os.path.join(r_dir, city)
        if not os.path.isdir(city_path):
            continue
        for slug in sorted(os.listdir(city_path)):
            slug_path = os.path.join(city_path, slug)
            if not os.path.isdir(slug_path):
                continue
            index_path = os.path.join(slug_path, "index.html")
            if not os.path.isfile(index_path):
                continue
            with open(index_path, encoding="utf-8", errors="ignore") as f:
                html = f.read()
            loc = f"https://thaidata.uk/r/{city}/{slug}/"
            canon = re.search(r'rel="canonical" href="([^"]*)"', html)
            if not canon or canon.group(1) != loc:
                continue  # alternate page (canonical elsewhere) — not indexable
            fsa_id = re.search(r'fsa-id" content="(\d+)"', html)
            if not fsa_id or fsa_id.group(1) not in current_ids:
                continue  # stale page — record no longer in current data
            if re.search(r'name="robots" content="noindex[^"]*"', html):
                continue  # closed venue / excluded — not indexable
            pages.append({
                "loc": loc,
                "changefreq": "monthly",
                "priority": "0.6",
            })
    return pages


def discover_city_pages() -> list[dict]:
    """Walk cities/*.html and return list of URL dicts."""
    cities_dir = os.path.join(REPO_DIR, "cities")
    pages = []
    if not os.path.isdir(cities_dir):
        return pages

    for fname in sorted(os.listdir(cities_dir)):
        if not fname.endswith(".html"):
            continue
        fpath = os.path.join(cities_dir, fname)
        with open(fpath, encoding="utf-8", errors="ignore") as f:
            page_html = f.read()
        # Skip noindexed pages (empty-state pages for cities with no current
        # listings) — submitting them would just create coverage warnings.
        if "<!-- CITIES-EMPTY-STATE" in page_html:
            continue
        if re.search(r'name="robots" content="noindex', page_html):
            continue
        city_slug = fname[:-5]  # strip .html
        pages.append({
            "loc": f"https://thaidata.uk/cities/{city_slug}",
            "changefreq": "monthly",
            "priority": "0.8",
        })
    return pages


def get_static_pages() -> list[dict]:
    """Return curated list of static/blog/tool pages."""
    pages = [
        # Core pages
        {"loc": "https://thaidata.uk/", "changefreq": "weekly", "priority": "1.0"},
        {"loc": "https://thaidata.uk/about", "priority": "0.9"},
        {"loc": "https://thaidata.uk/restaurants", "priority": "0.9"},
        {"loc": "https://thaidata.uk/r/", "priority": "0.8"},
        {"loc": "https://thaidata.uk/chains/", "priority": "0.8"},
        {"loc": "https://thaidata.uk/guides", "priority": "0.9"},
        {"loc": "https://thaidata.uk/learn", "priority": "0.9"},
        {"loc": "https://thaidata.uk/faq", "priority": "0.8"},
        {"loc": "https://thaidata.uk/contact", "priority": "0.8"},
        {"loc": "https://thaidata.uk/privacy", "priority": "0.7"},
        {"loc": "https://thaidata.uk/terms", "priority": "0.7"},
        {"loc": "https://thaidata.uk/brand-image", "priority": "0.7"},
        {"loc": "https://thaidata.uk/data-quality", "priority": "0.7"},
        {"loc": "https://thaidata.uk/dish-prices", "priority": "0.8"},
        {"loc": "https://thaidata.uk/sitemap-page", "priority": "0.5"},
        {"loc": "https://thaidata.uk/tools", "priority": "0.8"},
        {"loc": "https://thaidata.uk/nlw-report", "priority": "0.7"},

        # Blog / data-driven content
        {"loc": "https://thaidata.uk/how-many-thai-restaurants-uk", "priority": "0.8"},
        {"loc": "https://thaidata.uk/state-of-uk-thai-food-2026", "priority": "0.8"},
        {"loc": "https://thaidata.uk/thai-restaurants-city-breakdown-uk", "priority": "0.8"},
        {"loc": "https://thaidata.uk/thai-festivals-uk", "priority": "0.8"},
        {"loc": "https://thaidata.uk/songkran-uk", "priority": "0.8"},
        {"loc": "https://thaidata.uk/loy-krathong-uk", "priority": "0.8"},
        {"loc": "https://thaidata.uk/thai-chains-uk", "priority": "0.8"},
        {"loc": "https://thaidata.uk/thai-menu-price-index-uk", "priority": "0.8"},
        {"loc": "https://thaidata.uk/open-thai-restaurant-uk", "priority": "0.8"},
        {"loc": "https://thaidata.uk/open-thai-restaurant-timeline-uk", "priority": "0.7"},
        {"loc": "https://thaidata.uk/thai-chef-visa-uk", "priority": "0.7"},
        {"loc": "https://thaidata.uk/thai-food-trends-uk-2026", "priority": "0.7"},
        {"loc": "https://thaidata.uk/thai-delivery-profit-analysis-2026", "priority": "0.7"},
        {"loc": "https://thaidata.uk/thai-restaurant-costs-uk", "priority": "0.7"},
        {"loc": "https://thaidata.uk/thai-restaurant-delivery-commissions-uk", "priority": "0.7"},
        {"loc": "https://thaidata.uk/thai-restaurant-menu-pricing-uk", "priority": "0.7"},
        {"loc": "https://thaidata.uk/thai-restaurant-revenue-benchmarks-uk", "priority": "0.7"},
        {"loc": "https://thaidata.uk/thai-restaurant-gp-calculator", "priority": "0.7"},
        {"loc": "https://thaidata.uk/thai-restaurant-marketing-uk", "priority": "0.7"},
        {"loc": "https://thaidata.uk/thai-wholesale-suppliers-uk", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/khao-soi/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/som-tum-thai/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/pad-krapow/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/green-curry/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/tom-yum-goong/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/laab/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/pad-thai/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/massaman/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/tom-kha-gai/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/khao-man-gai/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/panang/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/pad-see-ew/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/khao-pad/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/mango-sticky-rice/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/gaeng-som/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/khao-kha-mu/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/yum-neua/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/tom-yum-noodle-soup/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/thai-iced-tea/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/red-curry/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/pad-kee-mao/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/chicken-satay/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/thai-fish-cakes/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/thai-iced-coffee/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/tab-tim-grob/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/yellow-curry/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/pad-prik-king/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/thai-banana-fritters/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/kanom-krok/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/thai-omelette/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/nam-tok/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/moo-ping/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/kanom-tuay/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/shrimp-cakes/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/thai-spring-rolls/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/gaeng-jued/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/cashew-chicken/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/pad-pak-bung/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/tom-saap/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/khao-tom/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/hoy-tod/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/yum-woon-sen/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/pad-kana-moo-krob/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/thai-lemon-iced-tea/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/rad-na/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/bamee-moo-daeng/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/khao-mok-gai/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/gai-tod-hat-yai/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/nom-yen/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/bua-loy/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/khao-khluk-kapi/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/som-tum-pu-pla-ra/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/yen-ta-fo/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/son-in-law-eggs/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/khao-na-pet/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/oliang/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/guay-tiew-ruea/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/gaeng-pa/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/pad-khing/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/pad-cha/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/lod-chong/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/cha-kiao-yen/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/gai-yang/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/pad-priew-wan/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/kluay-buat-chi/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/khao-pad-saparot/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/mee-krob/", "priority": "0.7"},
        {"loc": "https://thaidata.uk/recipes/kuay-jap/", "priority": "0.7"},

        # Tools
        {"loc": "https://thaidata.uk/tools/where-to-open-thai-restaurant-uk", "priority": "0.6"},
        {"loc": "https://thaidata.uk/tools/thai-restaurant-break-even-calculator", "priority": "0.6"},
        {"loc": "https://thaidata.uk/tools/thai-restaurant-market-report", "priority": "0.6"},
        {"loc": "https://thaidata.uk/tools/thai-competitor-radar", "priority": "0.6"},
        {"loc": "https://thaidata.uk/tools/thai-restaurant-hygiene-lookup", "priority": "0.6"},
        {"loc": "https://thaidata.uk/tools/thai-restaurant-staffing-calculator", "priority": "0.6"},
        {"loc": "https://thaidata.uk/tools/thai-restaurant-health-check", "priority": "0.6"},
        {"loc": "https://thaidata.uk/tools/thai-restaurant-valuation", "priority": "0.6"},
        {"loc": "https://thaidata.uk/tools/delivery-profit-calculator", "priority": "0.6"},
        {"loc": "https://thaidata.uk/tools/thai-ingredient-price-tracker", "priority": "0.6"},
        {"loc": "https://thaidata.uk/tools/thai-supplier-price-tracker", "priority": "0.6"},
        {"loc": "https://thaidata.uk/tools/thai-menu-price-elasticity-tester", "priority": "0.6"},
    ]
    return pages


def discover_html_pages(subdir: str, url_prefix: str, priority: str = "0.7",
                         changefreq: str = "monthly") -> list[dict]:
    """Discover HTML files in a subdirectory."""
    d = os.path.join(REPO_DIR, subdir)
    pages = []
    if not os.path.isdir(d):
        return pages
    for fname in sorted(os.listdir(d)):
        if not fname.endswith(".html") or fname == "index.html":
            continue
        slug = fname[:-5]  # strip .html
        pages.append({
            "loc": f"https://thaidata.uk/{url_prefix}/{slug}",
            "changefreq": changefreq,
            "priority": priority,
        })
    return pages


def write_sitemap(filename: str, urls: list[dict], with_lastmod: bool = True):
    """Write a sitemap XML file."""
    register_namespace()
    urlset = Element("urlset", xmlns=NS)

    for entry in urls:
        kwargs = {
            "loc": entry["loc"],
            "changefreq": entry.get("changefreq", "monthly"),
            "priority": entry.get("priority", "0.6"),
        }
        if with_lastmod:
            kwargs["lastmod"] = TODAY
        urlset.append(url_element(**kwargs))

    raw = tostring(urlset, encoding="unicode")
    pretty = minidom.parseString(raw).toprettyxml(indent="  ", encoding="UTF-8")
    # Remove the XML declaration line from minidom output (we add our own)
    lines = pretty.decode("utf-8").split("\n")
    # Remove first line (<?xml ...?>) and add our own
    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + "\n".join(lines[1:])

    out_path = os.path.join(REPO_DIR, filename)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(xml_str)
    return out_path


def discover_menu_pages() -> list[dict]:
    """Walk r/<city>/<slug>/menu/index.html and return full-menu page URLs.

    Menu pages are generated by scripts/build_menu_page.py and are identified by
    the name="thaidata-page" marker meta tag that generator writes. They are
    submitted at higher priority than the restaurant detail page, because a full
    menu is the page that actually satisfies the search intent ("<name> menu").
    """
    r_dir = os.path.join(REPO_DIR, "r")
    pages = []
    if not os.path.isdir(r_dir):
        return pages

    for city in sorted(os.listdir(r_dir)):
        city_path = os.path.join(r_dir, city)
        if not os.path.isdir(city_path):
            continue
        for slug in sorted(os.listdir(city_path)):
            index_path = os.path.join(city_path, slug, "menu", "index.html")
            if not os.path.isfile(index_path):
                continue
            with open(index_path, encoding="utf-8", errors="ignore") as f:
                html = f.read()
            if 'name="thaidata-page"' not in html:
                continue  # not a generated menu page
            if re.search(r'name="robots" content="noindex[^"]*"', html):
                continue
            loc = f"https://thaidata.uk/r/{city}/{slug}/menu/"
            canon = re.search(r'rel="canonical" href="([^"]*)"', html)
            if not canon or canon.group(1) != loc:
                continue  # alternate page (canonical elsewhere) — not indexable
            pages.append({
                "loc": loc,
                "changefreq": "weekly",
                "priority": "0.8",
            })
    return pages


def main():
    print("Generating sitemaps...")

    # ── Restaurant pages ──────────────────────────────────────────
    restaurant_urls = discover_restaurant_pages()

    # ── Full menu pages (auto-discovered) ─────────────────────────
    menu_urls = discover_menu_pages()

    write_sitemap("sitemap-r-restaurants.xml", restaurant_urls + menu_urls, with_lastmod=False)
    print(f"  sitemap-r-restaurants.xml: {len(restaurant_urls)} restaurant pages "
          f"+ {len(menu_urls)} menu pages")

    # ── Static + blog + tool pages ────────────────────────────────
    static_urls = get_static_pages()

    # ── City pages (auto-discovered) ──────────────────────────────
    city_urls = discover_city_pages()
    print(f"  City pages: {len([u for u in city_urls if '/cities/' in u['loc']])} city + {len([u for u in city_urls if '/r/' in u['loc']])} r/ hubs")

    # ── Chain pages (auto-discovered) ─────────────────────────────
    chain_urls = discover_html_pages("chains", "chains", priority="0.7")

    # ── Learn pages (auto-discovered) ─────────────────────────────
    learn_urls = discover_html_pages("learn", "learn", priority="0.7")

    # ── Combine pages sitemap ─────────────────────────────────────
    all_page_urls = static_urls + city_urls + chain_urls + learn_urls
    # Deduplicate by loc
    seen = set()
    deduped = []
    for u in all_page_urls:
        if u["loc"] not in seen:
            seen.add(u["loc"])
            deduped.append(u)
    write_sitemap("sitemap-pages.xml", deduped)
    print(f"  sitemap-pages.xml: {len(deduped)} total pages")

    # ── Sitemap index ─────────────────────────────────────────────
    register_namespace()
    sitemapindex = Element("sitemapindex", xmlns=NS)
    for sitemap_file in ["sitemap-pages.xml", "sitemap-r-restaurants.xml"]:
        sm = SubElement(sitemapindex, "sitemap")
        loc_el = SubElement(sm, "loc")
        loc_el.text = f"https://thaidata.uk/{sitemap_file}"
        lm = SubElement(sm, "lastmod")
        lm.text = TODAY

    raw = tostring(sitemapindex, encoding="unicode")
    pretty = minidom.parseString(raw).toprettyxml(indent="  ", encoding="UTF-8")
    lines = pretty.decode("utf-8").split("\n")
    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + "\n".join(lines[1:])

    with open(os.path.join(REPO_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(xml_str)
    print(f"  sitemap.xml: index file")

    # ── Summary ──────────────────────────────────────────────────
    total = len(restaurant_urls) + len(menu_urls) + len(deduped)
    print(f"\n✅ Sitemaps generated: {total:,} total URLs")


if __name__ == "__main__":
    main()
