"""Public catalog routes, independent of editorial publication permission."""

import hashlib
import re

from apworld_editorial import join_index_record


def public_catalog(worlds, overlays):
    active = [world for world in worlds if not world["disabled"]]
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
        result.append({
            **world,
            "editorial": editorial,
            "review_state": joined["review_state"],
            "detail_slug": slug,
            "detail_href": (editorial or {}).get("route_override", f"/apworlds/{slug}"),
            "detail_route_kind": (editorial or {}).get("route_kind", "spa"),
        })
    return result
