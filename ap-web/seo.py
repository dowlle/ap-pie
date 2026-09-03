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


#: One sentence pair naming what Archipelago Pie does and does not do. Kept
#: here so the structured data, llms.txt and the on-page copy cannot drift.
CAPABILITY_STATEMENT = (
    "Archipelago Pie collects player YAMLs in a collection room, and gives you the reviewed APWorld catalog and a YAML Builder for making them. It does not generate the multiworld and does not run game servers: you generate locally with the Archipelago Launcher, then host the server on archipelago.gg or your own machine."
)


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
                # Stated on every page so answer engines have a quotable
                # capability boundary. AP-Pie is repeatedly described by AI
                # answers as a multiworld host, which it is not.
                "description": CAPABILITY_STATEMENT,
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
                "description": CAPABILITY_STATEMENT,
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
