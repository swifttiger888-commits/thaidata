from pathlib import Path
from html import escape, unescape
import re

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_ZONE_NAMES = (
    "schema",
    "market-snapshot",
    "chain-presence",
    "postcode-areas",
    "faq",
)
_TOKENS = re.compile(r"\{(city_name|slug|meta_description)\}")
_SIGNATURE = "<!-- SHELL:location-v1 -->"
_BROWSE_START = "<!-- BEGIN Browse Restaurants -->"
_BROWSE_END = "<!-- END Browse Restaurants -->"


def _template(filename, values):
    source = (_TEMPLATE_DIR / filename).read_text(encoding="utf-8")
    return _TOKENS.sub(lambda match: values[match.group(1)], source)


def _county_slugs():
    source = (_TEMPLATE_DIR / "county-slugs.txt").read_text(
        encoding="utf-8"
    )
    return {
        line.strip()
        for line in source.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def _zone_pattern(name):
    return re.compile(
        re.escape("<!-- AUTO:" + name + " -->")
        + r".*?"
        + re.escape("<!-- END:AUTO:" + name + " -->"),
        re.DOTALL,
    )


def auto_zone_bytes(source):
    """Accept bytes; return complete, byte-exact marker-to-marker blocks."""
    result = {}
    positions = []
    for name in _ZONE_NAMES:
        start = ("<!-- AUTO:" + name + " -->").encode("ascii")
        end = ("<!-- END:AUTO:" + name + " -->").encode("ascii")
        if source.count(start) != 1 or source.count(end) != 1:
            raise ValueError("Expected exactly one AUTO zone: " + name)
        left = source.index(start)
        right = source.index(end, left) + len(end)
        result[name] = source[left:right]
        positions.append((left, right))
    if positions != sorted(positions):
        raise ValueError("AUTO zone order changed")
    for previous, following in zip(positions, positions[1:]):
        if previous[1] > following[0]:
            raise ValueError("Overlapping AUTO zones")
    return result


def _replace_shell_region(source, name, content):
    start = "<!-- SHELL:" + name + " -->"
    end = "<!-- END:SHELL:" + name + " -->"
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError("Expected exactly one shell region: " + name)
    left = source.index(start) + len(start)
    right = source.index(end, left)
    return source[:left] + "\n" + content + "\n    " + source[right:]


def _plain_text(fragment):
    return unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def _browse_block(source):
    if source.count(_BROWSE_START) != source.count(_BROWSE_END):
        raise ValueError("Unbalanced Browse markers")
    if source.count(_BROWSE_START) > 1:
        raise ValueError("Duplicate Browse blocks")
    if _BROWSE_START not in source:
        return ""
    left = source.index(_BROWSE_START)
    right = source.index(_BROWSE_END, left) + len(_BROWSE_END)
    return source[left:right]


def _locality_card(browse):
    # Use only explicit "locality • postcode" labels already in Browse.
    # Do not infer towns from postcode prefixes or split street addresses.
    localities = set()
    for fragment in re.findall(
        r"<span\b[^>]*>(.*?)</span>", browse, flags=re.DOTALL
    ):
        text = _plain_text(fragment)
        if " • " in text:
            locality, postcode = text.rsplit(" • ", 1)
            if locality and re.fullmatch(
                r"[A-Z]{1,2}[0-9][A-Z0-9]?"
                r"(?:\s*[0-9][A-Z]{2})?",
                postcode.strip(),
            ):
                localities.add(locality)

    if not localities:
        return ""

    items = "\n".join(
        "        <li>" + escape(name) + "</li>"
        for name in sorted(localities, key=str.casefold)
    )
    return (
        '    <section class="card localities" aria-labelledby="towns-title">\n'
        '      <h2 id="towns-title">Towns and villages in the listings</h2>\n'
        "      <p>Places explicitly named in the listing addresses below. "
        "This is not a complete list of places in the area.</p>\n"
        '      <ul class="locality-list">\n'
        + items
        + "\n      </ul>\n"
        '      <p><a href="#browse">Browse the restaurant listings</a></p>\n'
        "    </section>"
    )


def new_location_shell(city_name, slug):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError("Invalid location slug: " + repr(slug))

    description = (
        "Browse FSA-listed Thai restaurants in "
        + city_name
        + ", with restaurant listings and food hygiene information."
    )
    values = {
        "city_name": escape(city_name, quote=True),
        "slug": slug,
        "meta_description": escape(description, quote=True),
    }
    head = _template("location-head.html", values)
    opening = _template("location-opening.html", values)
    closing = _template("location-closing.html", values)

    if slug not in _county_slugs():
        opening = opening.replace(
            "County &amp; district directory", "Local area directory"
        ).replace(
            "Explore restaurants across the area's towns and villages.\n"
            "        These listings are grouped under this location "
            "in the FSA data;\n"
            "        they are not a single-city catchment.",
            "Explore Thai restaurant listings and food hygiene information.\n"
            "        Listings are grouped under this location in the FSA data.",
        ).replace(
            "<h1>Thai restaurants across ",
            "<h1>Thai restaurants in ",
        )

    zones = "\n".join(
        "<!-- AUTO:" + name + " -->\n"
        "<!-- END:AUTO:" + name + " -->"
        for name in _ZONE_NAMES
    )
    return (
        '<!DOCTYPE html>\n<html lang="en-GB">\n'
        "<!-- CITIES-MODE: programmatic -->\n"
        + head.rstrip()
        + "\n"
        + opening.rstrip()
        + "\n"
        + zones
        + "\n"
        + closing.lstrip()
    )


def finish_location_shell(source):
    """Run after BOTH AUTO and Browse generation, immediately before writing."""
    if _SIGNATURE not in source:
        return source

    before = auto_zone_bytes(source.encode("utf-8"))
    browse = _browse_block(source)

    if browse:
        # Browse is outside the five protected zones.
        if any(browse.encode("utf-8") in block for block in before.values()):
            raise ValueError("Browse unexpectedly occurs inside an AUTO zone")

        source = source.replace(browse, "", 1)

        # Decorative icons are redundant with visible business-type text.
        browse = re.sub(
            r'<i\b[^>]*\bclass="fas\b[^"]*"[^>]*>\s*</i>',
            "",
            browse,
            flags=re.DOTALL,
        )

    source = _replace_shell_region(source, "browse", browse)

    # Only confirmed county/district pages get the town-and-village card.
    is_county = (
        '<p class="eyebrow">County &amp; district directory</p>' in source
    )
    source = _replace_shell_region(
        source,
        "localities",
        _locality_card(browse) if is_county else "",
    )

    snapshot = before["market-snapshot"].decode("utf-8")
    count = re.search(
        r"There are\s*<strong>([0-9][0-9,]*)</strong>"
        r"\s*FSA-listed Thai businesses",
        snapshot,
    )
    summary = ""
    if count:
        # Preserve the existing generator's numeric subtitle hook exactly.
        summary = (
            '      <p class="sub">'
            + count.group(1)
            + " FSA-listed Thai businesses in this area.</p>"
        )
    source = _replace_shell_region(source, "summary", summary)

    after = auto_zone_bytes(source.encode("utf-8"))
    if before != after:
        raise AssertionError("Shell finalisation changed an AUTO zone")

    main_start = source.index('<main id="main" class="wrap">')
    main_end = source.index("</main>", main_start)
    for name in _ZONE_NAMES:
        start = source.index("<!-- AUTO:" + name + " -->")
        end = source.index("<!-- END:AUTO:" + name + " -->")
        if not main_start < start < end < main_end:
            raise AssertionError("AUTO zone escaped main: " + name)
    if source.index('<footer class="site-footer">') < main_end:
        raise AssertionError("Footer precedes main content")

    return source


def reshell_existing_bytes(original, city_name, slug):
    """One-off migration; preserve the entire original AUTO corridor."""
    before = auto_zone_bytes(original)
    source = original.decode("utf-8")

    corridor_start = source.index("<!-- AUTO:schema -->")
    corridor_end = (
        source.index("<!-- END:AUTO:faq -->")
        + len("<!-- END:AUTO:faq -->")
    )
    corridor = source[corridor_start:corridor_end]

    result = new_location_shell(city_name, slug)
    seed_start = result.index("<!-- AUTO:schema -->")
    seed_end = (
        result.index("<!-- END:AUTO:faq -->")
        + len("<!-- END:AUTO:faq -->")
    )
    result = result[:seed_start] + corridor + result[seed_end:]
    result = _replace_shell_region(
        result, "browse", _browse_block(source)
    )
    result = finish_location_shell(result)
    encoded = result.encode("utf-8")

    if before != auto_zone_bytes(encoded):
        raise AssertionError("Migration changed an AUTO zone")
    return encoded
