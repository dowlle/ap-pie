"""Project sections: one registry per project for navigation and breadcrumbs.

A project section (CTR Archipelago, Poképelago) groups the project hub, its
own pages and its guides, which moved from /guides into their section on
2026-09-25. Every page in a section shows the same section navigation, and
its visible breadcrumbs and BreadcrumbList structured data come from the
same trail, so the three cannot drift apart.

Items with `children` form a group: the group's own page opens the second
navigation row, and every child page shows the group as its parent in the
breadcrumbs. `external` items are shown in the navigation but never become
the current page or a breadcrumb.
"""
from __future__ import annotations

import config

SECTIONS: dict[str, dict] = {
    "ctr": {
        "name": "CTR Archipelago",
        "path": "/ctr",
        "items": [
            {"label": "Overview", "path": "/ctr"},
            {"label": "Download", "path": "/ctr/download"},
            {"label": "Setup guide", "path": "/ctr/setup"},
            {
                "label": "How it works",
                "path": "/ctr/reference",
                "crumb": "How it works",
                "children": [
                    {"label": "Warp pads", "path": "/ctr/reference/warp-pads"},
                    {"label": "Progression", "path": "/ctr/reference/progression"},
                    {"label": "Randomized content", "path": "/ctr/reference/randomized-content"},
                    {"label": "AP box locations", "path": "/ctr/reference/ap-boxes"},
                ],
            },
            {"label": "Release notes", "path": "/ctr/releases/0-2-0", "crumb": "0.2.0 release notes"},
            {"label": "Vanilla CTR on PC", "path": "/ctr/play-on-pc", "crumb": "Play CTR on PC"},
        ],
    },
    "poke": {
        "name": "Poképelago",
        "path": "/pokepelago",
        "items": [
            {"label": "Overview", "path": "/pokepelago"},
            {"label": "Setup guide", "path": "/pokepelago/setup"},
            {"label": "Twitch chat guessing", "path": "/pokepelago/twitch"},
            {"label": "Play Poképelago", "path": "https://pokepelago.ap-pie.com/", "external": True},
        ],
    },
}


def _owns(item: dict, path: str) -> bool:
    """True when `path` is the item's page or a page below it (AP box tracks)."""
    if item.get("external"):
        return False
    return path == item["path"] or path.startswith(item["path"] + "/")


def _match(section: dict, path: str) -> tuple[dict | None, dict | None]:
    """Return (top-level item, child item) that own `path`, most specific first."""
    for item in section["items"]:
        for child in item.get("children", []):
            if _owns(child, path):
                return item, child
    # The hub path owns everything below it, so only an exact hub match counts.
    for item in section["items"]:
        if item["path"] == section["path"]:
            if path == item["path"]:
                return item, None
        elif _owns(item, path):
            return item, None
    return None, None


def section_nav(key: str, path: str) -> dict:
    """Navigation for a page at `path`: the top row, plus the second row when
    the page belongs to a group."""
    section = SECTIONS[key]
    top, child = _match(section, path)
    items = [
        {
            "label": item["label"],
            "path": item["path"],
            "external": bool(item.get("external")),
            "current": item is top,
            "exact": item is top and child is None and path == item["path"],
        }
        for item in section["items"]
    ]
    sub = []
    if top is not None and top.get("children"):
        sub = [
            {"label": c["label"], "path": c["path"], "current": c is child,
             "exact": c is child and path == c["path"]}
            for c in top["children"]
        ]
    return {"key": key, "name": section["name"], "path": section["path"], "items": items, "sub": sub}


def trail(key: str, path: str, title: str, extra: list[tuple[str, str]] | None = None) -> list[dict]:
    """Breadcrumb trail from Home to the page, as [{"name", "path"}].

    Registered pages are named by their navigation label (or `crumb`);
    `title` names a page that is not in the registry. `extra` appends deeper
    levels below it (an AP box track page passes its track). The last entry
    is the page.
    """
    section = SECTIONS[key]
    top, child = _match(section, path)
    crumbs = [{"name": "Home", "path": "/"}, {"name": section["name"], "path": section["path"]}]
    if top is not None and top["path"] != section["path"]:
        crumbs.append({"name": top.get("crumb", top["label"]), "path": top["path"]})
    if child is not None:
        crumbs.append({"name": child.get("crumb", child["label"]), "path": child["path"]})
    for name, extra_path in extra or []:
        crumbs.append({"name": name, "path": extra_path})
    if crumbs[-1]["path"] != path:
        crumbs.append({"name": title, "path": path})
    return crumbs


def breadcrumb_node(crumbs: list[dict], canonical_path: str) -> dict:
    """schema.org BreadcrumbList for a trail. The first crumb is named after
    the site, as search engines show it in place of the domain."""
    base = config.PUBLIC_BASE_URL
    return {
        "@type": "BreadcrumbList",
        "@id": f"{base}{canonical_path}#breadcrumb",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": position,
                "name": "Archipelago Pie" if position == 1 else crumb["name"],
                "item": f"{base}{crumb['path']}",
            }
            for position, crumb in enumerate(crumbs, start=1)
        ],
    }


def context(key: str, path: str, title: str, extra: list[tuple[str, str]] | None = None) -> dict:
    """Template context for base.html: section navigation, breadcrumbs, and
    the matching BreadcrumbList node for the page's structured data."""
    crumbs = trail(key, path, title, extra)
    return {
        "section": section_nav(key, path),
        "crumbs": crumbs,
        "breadcrumb_node": breadcrumb_node(crumbs, path),
    }


def section_paths(key: str) -> list[str]:
    """Every internal page path in a section, hub first."""
    section = SECTIONS[key]
    paths = []
    for item in section["items"]:
        if not item.get("external"):
            paths.append(item["path"])
        paths.extend(c["path"] for c in item.get("children", []))
    return paths
