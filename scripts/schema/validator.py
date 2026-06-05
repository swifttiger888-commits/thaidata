"""Schema validation — JSON Schema validation + content–schema matching.

Policies enforced:
- Every schema block must be valid JSON and valid against its JSON Schema.
- Every user-meaningful schema fact must have a visible on-page equivalent.
- AggregateRating is forbidden for FSA data (use additionalProperty instead).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

# Fields exempt from content–schema matching (purely technical)
EXEMPT_FIELDS: set[str] = {
    "@context",
    "@type",
    "@id",
    "itemid",
    "url",
    "position",
    "sameAs",
}

# User-meaningful schema paths that must have on-page equivalents
# Each is a dot-separated path to a field value
USER_MEANINGFUL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"itemListElement\[\d+\]\.item\.name$"),
    re.compile(r"itemListElement\[\d+\]\.item\.additionalProperty\.value$"),
    re.compile(r"itemListElement\[\d+\]\.item\.address\.addressLocality$"),
    re.compile(r"mainEntity\[\d+\]\.name$"),
    re.compile(r"mainEntity\[\d+\]\.acceptedAnswer\.text$"),
    re.compile(r"itemListElement\[\d+\]\.name$"),
]


def validate_schema(
    schema_dict: dict[str, Any],
    schema_path: str | Path | None = None,
) -> list[str]:
    """Validate a schema dict.

    Checks:
    1. No AggregateRating with FSA-related content (policy violation).
    2. Valid JSON (always true for dicts, but ensures structure).
    3. If a JSON Schema file is provided, validates against it.

    Args:
        schema_dict: The schema.org dict to validate.
        schema_path: Optional path to a .schema.json file.

    Returns:
        List of error strings. Empty list = valid.
    """
    errors: list[str] = []

    # Policy: No AggregateRating for FSA data
    if _has_fsa_aggregate_rating(schema_dict):
        errors.append(
            "POLICY VIOLATION: AggregateRating used with FSA hygiene data. "
            "FSA scores are single official inspections, not user-review aggregates. "
            "Use additionalProperty instead."
        )

    # JSON Schema validation (if schema file provided)
    if schema_path:
        schema_path = Path(schema_path)
        if schema_path.exists():
            with open(schema_path) as f:
                schema = json.load(f)
            schema_errors = _validate_against_schema(schema_dict, schema)
            errors.extend(schema_errors)
        else:
            errors.append(f"Schema file not found: {schema_path}")

    return errors


def _has_fsa_aggregate_rating(d: Any, _path: str = "") -> bool:
    """Recursively check for AggregateRating containing FSA-related content."""
    if not isinstance(d, dict):
        return False

    is_aggregate = d.get("@type") == "AggregateRating"
    has_fsa_context = False

    for key, value in d.items():
        if isinstance(value, str) and "FSA" in value.upper():
            has_fsa_context = True
        if isinstance(value, (dict, list)):
            if _has_fsa_aggregate_rating(value, f"{_path}.{key}"):
                return True

    return is_aggregate and has_fsa_context


def _validate_against_schema(
    instance: dict[str, Any],
    schema: dict[str, Any],
) -> list[str]:
    """Minimal JSON Schema validation (draft-07 core features).

    Handles: type, required, properties, items, enum, oneOf, anyOf.
    Falls back to jsonschema library if available, otherwise does basic checks.
    """
    errors: list[str] = []

    try:
        import jsonschema  # type: ignore[import-untyped]

        try:
            validator = jsonschema.Draft7Validator(schema)
            validation_errors = list(validator.iter_errors(instance))
            for ve in validation_errors:
                errors.append(f"Schema validation error at {'/'.join(str(p) for p in ve.absolute_path)}: {ve.message}")
            return errors
        except jsonschema.exceptions.SchemaError as e:  # type: ignore[attr-defined]
            errors.append(f"Invalid JSON Schema: {e}")
            return errors
    except ImportError:
        pass  # Fall through to basic checks

    # Basic checks (no jsonschema library)
    if "required" in schema:
        for field in schema["required"]:
            if field not in instance:
                errors.append(f"Missing required field: {field}")

    if "type" in schema:
        expected = schema["type"]
        actual = type(instance).__name__
        if actual != expected:
            errors.append(f"Type mismatch: expected {expected}, got {actual}")

    return errors


def validate_content_schema_match(
    html_text: str,
    schema_dict: dict[str, Any],
    raw_html: str | None = None,
) -> list[str]:
    """Validate that user-meaningful schema facts appear in visible HTML.

    Args:
        html_text: HTML body with tags and scripts stripped.
        schema_dict: The schema.org dict to check.
        raw_html: Optional raw HTML for checking href/URL matches (breadcrumbs).

    Returns:
        List of missing-field error strings. Empty list = all pass.
    """
    errors: list[str] = []
    flat = _flatten_schema(schema_dict)

    for path, value in flat:
        skip = False
        for exempt in EXEMPT_FIELDS:
            if exempt in path:
                skip = True
                break

        # Check if this is a user-meaningful field
        is_meaningful = any(p.search(path) for p in USER_MEANINGFUL_PATTERNS)

        # Also consider breadcrumb names meaningful if they don't have href fallback
        is_breadcrumb_name = (
            ("itemListElement[" in path or ".itemListElement[" in path)
            and ".name" in path
            and ".item." not in path
        )

        if skip or not (is_meaningful or is_breadcrumb_name):
            continue

        if isinstance(value, str) and value.strip():
            val_lower = value.strip().lower()

            # Check visible text
            if val_lower in html_text.lower():
                continue

            # For breadcrumb names, also check if the corresponding URL has an href in raw HTML
            if is_breadcrumb_name and raw_html and _breadcrumb_url_exists(raw_html, flat, path, value):
                continue

            errors.append(
                f"Content–schema mismatch: '{value}' (at {path}) "
                f"not found in visible page content"
            )

    return errors


def _breadcrumb_url_exists(
    raw_html: str,
    flat: list[tuple[str, Any]],
    name_path: str,
    name_value: str,
) -> bool:
    """Check if the breadcrumb URL for a given name exists as an href in the HTML."""
    # Find the corresponding .item or .item.url path
    # name_path looks like "itemListElement[0].name"
    # We want "itemListElement[0].item"
    base_path = name_path.rsplit(".", 1)[0]  # "itemListElement[0]"
    item_url_path = f"{base_path}.item"

    for p, v in flat:
        if p == item_url_path and isinstance(v, str):
            # Check if this URL appears as an href in the HTML
            from urllib.parse import urlparse
            parsed = urlparse(v)
            # Check for bare path
            if parsed.path in raw_html:
                return True
            # Check full URL
            if v in raw_html:
                return True
    return False


def _flatten_schema(
    d: Any,
    parent_path: str = "",
    sep: str = ".",
) -> list[tuple[str, Any]]:
    """Recursively flatten a schema dict to (dot_path, value) pairs.

    List items use [index] notation: itemListElement[0].item.name
    """
    results: list[tuple[str, Any]] = []

    if isinstance(d, dict):
        for key, value in d.items():
            path = f"{parent_path}{sep}{key}" if parent_path else key
            results.append((path, value))
            if isinstance(value, (dict, list)):
                results.extend(_flatten_schema(value, path, sep))
    elif isinstance(d, list):
        for i, item in enumerate(d):
            path = f"{parent_path}[{i}]"
            results.append((path, item))
            if isinstance(item, (dict, list)):
                results.extend(_flatten_schema(item, path, sep))

    return results


def strip_html_body(html: str) -> str:
    """Strip tags, scripts, styles from HTML to get visible text."""
    # Remove script and style blocks
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Remove all tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Remove comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()
