#!/usr/bin/env python3
"""Batch menu builder for ThaiData UK.

Takes the national site scan (/tmp/national_scan.json) and turns every venue with
an owner-published menu into a menu page.

Design rules (see skill restaurant-menu-extraction):
  * never invent: extraction returns exactly what is printed, null when unreadable
  * skip-and-report beats publish-with-gaps: 0 dishes, no prices, or duplicates
    leaves the venue out and names the reason
  * never overwrite an existing menu output unless --force
  * never republish aggregator content (Just Eat / Uber Eats / Foodhub): only the
    venue's own site is scanned

Usage:
    python3 scripts/batch_menus.py --limit 6 --dry-run
    python3 scripts/batch_menus.py --types html_menu,text_pdf
    python3 scripts/batch_menus.py --all
"""
from __future__ import annotations

import argparse
import base64
import html as _html
import json
import os
import re
import subprocess
import signal
import socket
import sys
import time
import urllib.request
from collections import Counter

REPO = '/opt/thaidata-repo'
SCAN = '/tmp/national_scan.json'
WORK = '/tmp/menu_batch'
MODEL = 'google/gemini-3.8-flash'
UA = {'User-Agent': 'Mozilla/5.0 (compatible; ThaiDataBot/1.0; +https://thaidata.uk/about)'}
socket.setdefaulttimeout(30)  # no socket read may hang the queue
KEY = None
for line in open('/root/.hermes/.env'):
    if line.startswith('OPENROUTER_API_KEY'):
        KEY = line.split('=', 1)[1].strip().strip('"').strip("'")

STRUCT_PROMPT = """Below is the text of a restaurant menu. Extract it as JSON.

Rules:
- Copy names, descriptions and prices exactly as written. Never invent or tidy.
- A heading is the section title only; never put a price in a heading.
- If a heading prints one price for the whole section, put it in section_price.
- If a dish has no printed price, use null.
- Ignore opening hours, allergy disclaimers, delivery blurb and contact details.

Return STRICT JSON, no fence:
{"sections":[{"name":"<heading>","section_price":"<price or null>",
  "items":[{"name":"<dish>","description":"<as printed or empty>","price":"<as printed or null>",
            "vegetarian":<true|false>}]}],
 "pricing_notes":["lines that price a whole meal, copied exactly"]}"""

VISION_PROMPT = """This is a page (or band) of a restaurant menu. Transcribe ONLY what is visibly printed.

Rules:
- A heading is the printed section title only. Never include a price in a heading.
- If a heading prints one price for the whole section, put it in section_price.
- Never guess a price. Unreadable -> null and list it in unreadable.

Return STRICT JSON, no fence:
{"sections":[{"name":"<heading>","section_price":"<price or null>",
  "items":[{"num":"<number or empty>","name":"<dish>","description":"<as printed or empty>",
            "price":"<exactly as printed or null>","vegetarian":<true|false>}]}],
 "unreadable":["..."],
 "pricing_notes":["lines that price a meal/section, copied exactly"]}"""


def slugify(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize('NFC', (s or '').lower().strip())
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[-\s]+', '-', s)
    return s.strip('-')


# ---------------------------------------------------------------- model calls

def llm(messages, timeout=100):
    payload = {'model': MODEL, 'temperature': 0, 'messages': messages,
               'response_format': {'type': 'json_object'}}
    req = urllib.request.Request('https://openrouter.ai/api/v1/chat/completions',
                                 data=json.dumps(payload).encode(),
                                 headers={'Authorization': 'Bearer ' + KEY,
                                          'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read())
    try:
        u = d.get('usage') or {}
        with open('/tmp/menu_batch/usage.jsonl', 'a') as f:
            f.write(json.dumps({'model': MODEL, 'prompt': u.get('prompt_tokens'),
                                'completion': u.get('completion_tokens'),
                                'cost': u.get('cost'), 'ts': time.time()}) + '\n')
    except Exception:
        pass
    txt = d['choices'][0]['message']['content'].strip()
    txt = re.sub(r'^```(?:json)?|```$', '', txt, flags=re.M).strip()
    return json.loads(txt)


def llm_text(text):
    return llm([{'role': 'user', 'content': STRUCT_PROMPT + '\n\n---\n' + text[:20000]}])


def llm_image(path):
    from PIL import Image
    try:
        im = Image.open(path).convert('RGB')
        if im.width > 1400:
            im = im.resize((1400, int(im.height * 1400 / im.width)), Image.LANCZOS)
        p2 = path + '.conv.jpg'
        im.save(p2, 'JPEG', quality=90)
        path = p2
    except Exception:
        pass
    b64 = base64.b64encode(open(path, 'rb').read()).decode()
    return llm([{'role': 'user', 'content': [
        {'type': 'text', 'text': VISION_PROMPT},
        {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b64}}]}])


# ---------------------------------------------------------------- fetch utils

class Resp:
    def __init__(self, status, body, text=None):
        self.status_code = status
        self.content = body
        self.text = text if text is not None else body.decode('utf-8', 'replace')


def get(url, timeout=30):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return Resp(r.status, r.read())
    except Exception:
        return None


def download(url, dest, timeout=90):
    r = get(url, timeout=timeout)
    if r is None or r.status_code >= 400:
        return None
    with open(dest, 'wb') as f:
        f.write(r.content)
    return dest if os.path.getsize(dest) > 1000 else None


# ---------------------------------------------------------------- extraction

def from_html_menu(url):
    """Menu page HTML: prefer JSON-LD Menu, else give the text to the model."""
    r = get(url)
    if r is None or r.status_code >= 400:
        return None, 'fetch failed'
    h = r.text
    m = re.search(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', h, re.S)
    if m:
        for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', h, re.S):
            try:
                d = json.loads(block)
            except Exception:
                continue
            cand = d if isinstance(d, list) else [d]
            for c in cand:
                if isinstance(c, dict) and c.get('@type') == 'Menu':
                    return normalise_schema_menu(c), 'json-ld'
    txt = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', h, flags=re.S)
    txt = re.sub(r'<[^>]+>', '\n', txt)
    txt = re.sub(r'\n\s*\n+', '\n', txt)
    if len(txt) < 400:
        return None, 'no text'
    return normalise(llm_text(txt)), 'model-html'


def normalise_schema_menu(m):
    sections = []
    for s in m.get('hasMenuSection') or []:
        items = []
        for it in s.get('hasMenuItem') or []:
            offers = it.get('offers') or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            price = offers.get('price') if isinstance(offers, dict) else None
            items.append({'name': it.get('name', ''), 'description': it.get('description', ''),
                          'price': ('£' + str(price)) if price else None})
        if items:
            sections.append({'name': s.get('name', 'Menu'), 'section_price': None, 'items': items})
    return {'sections': sections, 'pricing_notes': []}


def from_text_pdf(url, dest):
    p = download(url, dest)
    if not p:
        return None, 'download failed'
    try:
        o = subprocess.run(['pdftotext', '-layout', p, '-'], capture_output=True, timeout=120)
        txt = o.stdout.decode('utf-8', 'replace')
    except Exception as e:
        return None, f'pdftotext {e}'
    if len(re.sub(r'\s+', '', txt)) < 200:
        return None, 'no text layer'
    return normalise(llm_text(txt)), 'text-pdf'


def from_image_pdf(url, dest):
    p = download(url, dest)
    if not p:
        return None, 'download failed'
    out = dest + '_pg'
    subprocess.run(['pdftoppm', '-r', '150', '-png', p, out], capture_output=True, timeout=240)
    pages = sorted(f for f in os.listdir(os.path.dirname(out))
                   if f.startswith(os.path.basename(out)) and f.endswith('.png'))
    if not pages:
        return None, 'render failed'
    merged = {'sections': [], 'pricing_notes': []}
    for pg in pages[:6]:
        try:
            d = llm_image(os.path.join(os.path.dirname(out), pg))
        except Exception:
            continue
        merged['sections'] += d.get('sections') or []
        merged['pricing_notes'] += d.get('pricing_notes') or []
    return normalise(merged), 'image-pdf'


def from_image_menu(url):
    """Menu images. The scan often records the image file itself, not a page."""
    if re.search(r'\.(?:jpe?g|png|webp)(?:\?|$)', url, re.I):
        dest = os.path.join(WORK, 'direct.jpg')
        os.makedirs(WORK, exist_ok=True)
        p = download(url, dest)
        if not p:
            return None, 'download failed'
        try:
            d = llm_image(p)
        except Exception as e:
            return None, f'vision failed {str(e)[:50]}'
        return normalise(d), 'image-direct'
    r = get(url)
    if r is None:
        return None, 'fetch failed'
    base = url.rsplit('/', 1)[0]
    imgs = [u for u in re.findall(r'(?:src|data-src)=["\']([^"\']+)', r.text, re.I)
            if re.search(r'menu', u, re.I)]
    imgs = [u if u.startswith('http') else base + '/' + u.lstrip('/') for u in imgs][:6]
    if not imgs:
        return None, 'no menu images'
    merged = {'sections': [], 'pricing_notes': []}
    for i, u in enumerate(imgs):
        ext = '.jpg'
        dest = os.path.join(WORK, f'img_{i}{ext}')
        p = download(u, dest)
        if not p:
            continue
        try:
            d = llm_image(p)
        except Exception:
            continue
        merged['sections'] += d.get('sections') or []
        merged['pricing_notes'] += d.get('pricing_notes') or []
    return normalise(merged), 'image-menu'


def normalise(raw):
    """Clean model output into the generator schema, applying section prices."""
    if isinstance(raw, list):
        raw = {'sections': raw}
    sections = []
    notes = [n for n in (raw.get('pricing_notes') or []) if n]
    seen = set()
    for s in raw.get('sections') or []:
        name = (s.get('name') or 'Menu').strip()
        sp = s.get('section_price')
        sp = ('£' + str(sp).lstrip('£')) if sp else None
        items = []
        for it in s.get('items') or []:
            # Model output sometimes hands back HTML entities ("&amp;"): unescape
            # once here so the page escaper doesn't double-escape into "&amp;amp;".
            nm = _html.unescape((it.get('name') or '')).strip()
            # "24. Gaeng Phed" -> num "24", name "Gaeng Phed": the page prints the
            # number in its own span, so leaving it in the name makes the render
            # guard see a different dish.
            num_m = re.match(r'^(\d{1,3})[.)]\s*(.+)$', nm)
            num = ''
            if num_m:
                num, nm = num_m.group(1), num_m.group(2).strip()
            if not nm or nm.lower() in seen:
                continue
            seen.add(nm.lower())
            price = it.get('price')
            price = ('£' + str(price).lstrip('£')) if price else sp
            row = {'name': nm, 'description': _html.unescape((it.get('description') or '')).strip(), 'price': price}
            if num:
                row['num'] = num
            if it.get('vegetarian'):
                row['vegetarian'] = True
            items.append(row)
        if items:
            sections.append({'name': name, 'items': items})
    return {'sections': sections, 'pricing_notes': notes}


# ---------------------------------------------------------------- build

def validate(sections):
    items = [i for s in sections for i in s['items']]
    # A handful of dishes almost always means a partial capture (one tab, one
    # column, or a page that only printed the specials). Publishing five dishes
    # as "the full menu" is worse than publishing none.
    if len(items) < 8:
        return f'thin: only {len(items)} items'
    priced = sum(1 for i in items if i.get('price'))
    if priced / len(items) < 0.5:
        return f'{priced}/{len(items)} priced'
    return None


def build_one(rec, force=False):
    name, city, fsa = rec['name'], rec['city'], str(rec['id'])
    res = rec['result']
    typ = res['type']
    slug = slugify(name)
    out_json = os.path.join(REPO, 'data', 'menus', f'{slug}-{slugify(city)}.json')
    if os.path.exists(out_json) and not force:
        return 'skip', 'already built'
    os.makedirs(WORK, exist_ok=True)
    try:
        if typ == 'html_menu':
            data, how = from_html_menu(res['url'])
        elif typ == 'text_pdf':
            data, how = from_text_pdf(res['url'], os.path.join(WORK, f'{slug}.pdf'))
        elif typ == 'image_pdf':
            data, how = from_image_pdf(res['url'], os.path.join(WORK, f'{slug}.pdf'))
        elif typ == 'image_menu':
            data, how = from_image_menu(res['url'])
        else:
            return 'skip', f'type {typ}'
    except Exception as e:
        return 'error', str(e)[:80]
    if not data or not data.get('sections'):
        return 'skip', how or 'nothing extracted'
    problem = validate(data['sections'])
    if problem:
        return 'skip', problem
    listing = find_listing(city, name)
    if not listing:
        return 'skip', 'no listing page'
    menu_json = {
        'restaurant': name, 'city': city, 'fsa_id': fsa,
        'address': listing['address'],
        'source': res['url'], 'source_label': "the restaurant's own menu",
        'checked': time.strftime('%Y-%m-%d'),
        'categories': {s['name']: s['items'] for s in data['sections']},
        'pricing_notes': data.get('pricing_notes') or [],
    }
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    json.dump(menu_json, open(out_json, 'w'), indent=1, ensure_ascii=False)
    dst_dir = os.path.join(REPO, 'r', listing['city_slug'], listing['slug'], 'menu')
    os.makedirs(dst_dir, exist_ok=True)
    r = subprocess.run([os.path.join(REPO, '.venv/bin/python'), 'scripts/build_menu_page.py',
                        out_json, os.path.join('r', listing['city_slug'], listing['slug'], 'menu', 'index.html')],
                       cwd=REPO, capture_output=True, text=True)
    if r.returncode != 0:
        return 'error', (r.stderr or '').strip().splitlines()[-1][:90]
    return 'built', f"{sum(len(s['items']) for s in data['sections'])} items ({how})"


def find_listing(city, name):
    cs, ns = slugify(city), slugify(name)
    p = os.path.join(REPO, 'r', cs, ns, 'index.html')
    if os.path.exists(p):
        try:
            h = open(p, encoding='utf-8', errors='ignore').read(4000)
            m = re.search(r'"streetAddress":\s*"([^"]+)"', h)
            return {'city_slug': cs, 'slug': ns, 'address': m.group(1) if m else city}
        except Exception:
            return {'city_slug': cs, 'slug': ns, 'address': city}
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--types', default='html_menu,text_pdf,image_pdf,image_menu')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--only', type=int, default=0, help='process a single 1-based target index')
    args = ap.parse_args()

    scan = json.load(open(SCAN))
    wanted = set(args.types.split(','))
    targets = [x for x in scan if x['result']['type'] in wanted]
    if args.only:
        targets = targets[args.only - 1:args.only]
    elif args.limit:
        targets = targets[:args.limit]
    print(f'targets: {len(targets)} of {len(scan)} scanned')
    if args.dry_run:
        c = Counter(x['result']['type'] for x in targets)
        print('by type:', dict(c))
        return

    t0 = time.time()
    report = []
    class _Timeout(BaseException):
        # BaseException on purpose: every extraction helper wraps its own work in
        # `except Exception`, which would otherwise swallow the watchdog.
        pass

    def _alarm(signum, frame):
        raise _Timeout()

    signal.signal(signal.SIGALRM, _alarm)

    for i, rec in enumerate(targets, 1):
        # A single slow host must not stall the whole run: some menu pages hang
        # on a socket read or a 6-page image PDF takes minutes. Cap each venue.
        signal.alarm(120)
        try:
            status, detail = build_one(rec, force=args.force)
        except _Timeout:
            status, detail = 'skip', 'per-venue timeout'
        except Exception as e:
            status, detail = 'error', str(e)[:80]
        finally:
            signal.alarm(0)
        report.append({'name': rec['name'], 'city': rec['city'], 'type': rec['result']['type'],
                       'status': status, 'detail': detail})
        print(f"[{i}/{len(targets)}] {rec['name'][:28]:28} {rec['result']['type']:11} {status:6} {detail}", flush=True)
        json.dump(report, open(os.path.join(WORK, 'report.json'), 'w'), indent=1)
    c = Counter(r['status'] for r in report)
    print(f"\n=== done in {(time.time()-t0)/60:.1f} min ===")
    print(dict(c))


if __name__ == '__main__':
    main()
