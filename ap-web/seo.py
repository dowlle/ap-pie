"""Shared JSON-LD builders for public, indexable pages.

Keep the entity identifiers stable across routes. Page-specific nodes reference
these entities instead of redefining disconnected organizations and authors.
"""

from __future__ import annotations


def _base(base_url: str) -> str:
    return base_url.rstrip("/")


def organization_id(base_url: str) -> str:
    return f"{_base(base_url)}/#organization"


def website_id(base_url: str) -> str:
    return f"{_base(base_url)}/#website"


def author_id(base_url: str) -> str:
    return f"{_base(base_url)}/#appie"


def graph(base_url: str, *nodes: dict) -> dict:
    base = _base(base_url)
    return {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Organization",
                "@id": organization_id(base),
                "name": "Archipelago Pie",
                "url": f"{base}/",
                "logo": {
                    "@type": "ImageObject",
                    "url": f"{base}/archipelago-favicon.png",
                },
            },
            {
                "@type": "WebSite",
                "@id": website_id(base),
                "name": "Archipelago Pie",
                "url": f"{base}/",
                "publisher": {"@id": organization_id(base)},
                "inLanguage": "en",
            },
            *nodes,
        ],
    }


def author(base_url: str) -> dict:
    return {
        "@type": "Person",
        "@id": author_id(base_url),
        "name": "Appie",
        "worksFor": {"@id": organization_id(base_url)},
    }


def page(base_url: str, page_type: str, url: str, name: str, description: str) -> dict:
    return {
        "@type": page_type,
        "@id": f"{url}#page",
        "url": url,
        "name": name,
        "description": description,
        "isPartOf": {"@id": website_id(base_url)},
        "publisher": {"@id": organization_id(base_url)},
        "inLanguage": "en",
    }
