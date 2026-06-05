"""Schema builder modules for city pages.

Each builder returns a validated Python dict ready for JSON serialization.
All builders accept raw data from restaurants.json and return schema.org-compliant structures.
"""
from scripts.schema.local_business import build_restaurant_list
from scripts.schema.faq_page import build_faq_page
from scripts.schema.breadcrumb import build_breadcrumb
from scripts.schema.city_entity import build_city_entity
from scripts.schema.validator import validate_schema, validate_content_schema_match

__all__ = [
    "build_restaurant_list",
    "build_faq_page",
    "build_breadcrumb",
    "build_city_entity",
    "validate_schema",
    "validate_content_schema_match",
]
