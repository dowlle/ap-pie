"""Public catalog routes, independent of editorial publication permission."""

import hashlib
import re
from collections import Counter

from apworld_editorial import join_index_record


def public_catalog(worlds, overlays):
    active = [world for world in worlds if not world["disabled"]]
    display_counts = Counter(world["display_name"] for world in active)
    reserved = {record.slug for record in overlays.values()}
    slugs = {}
    for world in active:
        name = world["name"]
        record = overlays.get(name)
        base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "world"
        # Reserve editorial slugs, including unpublished records, so later
        # publication cannot take another world's URL.
        slugs[name] = record.slug if record else base
    counts = {}
    for slug in slugs.values():
        counts[slug] = counts.get(slug, 0) + 1
    result = []
    for world in active:
        name = world["name"]
        slug = slugs[name]
        if name not in overlays and (counts[slug] > 1 or slug in reserved):
            slug += "-" + hashlib.sha256(name.encode()).hexdigest()
        joined = join_index_record(world, overlays)
        editorial = joined["editorial"]
        label = world["display_name"]
        if display_counts[label] > 1:
            label += f" ({name})"
        title = f"{label} Archipelago APWorld | Archipelago Pie"
        if len(title) > 65:
            title = f"{label} | APWorld"
        if len(title) > 65:
            title = f"{label[:48].rstrip()}… | APWorld"
        description = f"{label} for Archipelago: versions, downloads, setup links, and recorded security review and generation evidence."
        if len(description) > 150:
            description = f"{label}: Archipelago APWorld versions, downloads, setup links and recorded evidence."
        result.append({
            **world,
            "editorial": editorial,
            "review_state": joined["review_state"],
            "detail_slug": slug,
            "detail_href": (editorial or {}).get("route_override", f"/apworlds/{slug}"),
            "detail_route_kind": (editorial or {}).get("route_kind", "spa"),
            "detail_title": title,
            "detail_description": description,
        })
    return result
