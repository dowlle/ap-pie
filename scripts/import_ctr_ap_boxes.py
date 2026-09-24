"""Import the CTR AP box location pictures into the site.

Reads the render manifest (manifest.csv from the CTR editor-shots tool) and
writes, per box, a full-size WebP and a 480x270 thumbnail under
ap-web/frontend/public/img/ctr/ap-boxes/<track-slug>/, plus the page data file
ap-web/guides/ctr-reference/ap-boxes.json. A track map
(<track-slug>/<track-slug>-map.svg), when present, is copied to
ap-web/templates/ctr/ap-box-maps/<track-slug>.svg for inline use. Re-running after a re-shoot only
rewrites pictures whose source PNG changed (tracked by sha256 in the data file).

Usage:
    python scripts/import_ctr_ap_boxes.py <dir with manifest.csv>
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
IMG_DIR = ROOT / "ap-web" / "frontend" / "public" / "img" / "ctr" / "ap-boxes"
DATA_FILE = ROOT / "ap-web" / "guides" / "ctr-reference" / "ap-boxes.json"
MAP_DIR = ROOT / "ap-web" / "templates" / "ctr" / "ap-box-maps"

FULL_QUALITY = 80
THUMB_SIZE = (480, 270)
THUMB_QUALITY = 75

# Retail hub of each track, in the order the hubs open in Adventure mode.
HUBS: list[tuple[str, list[str]]] = [
    ("N. Sanity Beach", ["Crash Cove", "Roo's Tubes", "Mystery Caves", "Sewer Speedway"]),
    ("The Lost Ruins", ["Coco Park", "Tiger Temple", "Papu's Pyramid", "Dingo Canyon"]),
    ("Glacier Park", ["Blizzard Bluff", "Dragon Mines", "Polar Pass", "Tiny Arena"]),
    ("Citadel City", ["N. Gin Labs", "Cortex Castle", "Hot Air Skyway", "Oxide Station"]),
    ("Gemstone Valley", ["Slide Coliseum", "Turbo Track"]),
]

# Boxes that only exist at a higher shortcut_knowledge setting
# (SK_REQUIRED_TIER in the apworld's item_boxes.py).
SHORTCUT_KNOWLEDGE: dict[tuple[str, int], str] = {
    ("Tiger Temple", 5): "Medium",
    ("Coco Park", 7): "Medium",
    ("Dragon Mines", 2): "Medium",
    ("Sewer Speedway", 2): "Medium",
    ("Sewer Speedway", 3): "Medium",
    ("Papu's Pyramid", 6): "Medium",
    ("Papu's Pyramid", 12): "Medium",
    ("Papu's Pyramid", 7): "Hard",
    ("Papu's Pyramid", 10): "Hard",
    ("Polar Pass", 9): "Hard",
    ("Hot Air Skyway", 8): "Hard",
    ("Oxide Station", 6): "Hard",
}

# Item requirements per box, copied from BOX_RULES in the apworld's
# item_boxes.py (identical in 0.2.0 and main): (Progressive Boost count,
# one upgrade of each stat). Each term only applies while its option is on.
BOX_RULES: dict[tuple[str, int], tuple[int, bool]] = {
    ("Crash Cove", 4): (1, False), ("Crash Cove", 9): (1, False), ("Crash Cove", 10): (1, False),
    ("Sewer Speedway", 2): (1, False), ("Sewer Speedway", 3): (1, False),
    ("Papu's Pyramid", 6): (1, False), ("Papu's Pyramid", 12): (1, False),
    ("Papu's Pyramid", 7): (1, True), ("Papu's Pyramid", 10): (1, True),
    ("Polar Pass", 14): (1, False), ("Polar Pass", 15): (1, False), ("Polar Pass", 9): (1, True),
    ("Cortex Castle", 10): (1, False), ("Cortex Castle", 11): (2, False),
    ("N. Gin Labs", 4): (2, False), ("N. Gin Labs", 5): (2, False), ("N. Gin Labs", 6): (2, False),
    ("N. Gin Labs", 7): (2, False), ("N. Gin Labs", 8): (2, False), ("N. Gin Labs", 9): (2, False),
    ("N. Gin Labs", 14): (2, False), ("N. Gin Labs", 15): (2, False),
    ("Oxide Station", 6): (0, True), ("Oxide Station", 13): (2, False),
    ("Hot Air Skyway", 1): (2, False), ("Hot Air Skyway", 2): (2, False), ("Hot Air Skyway", 3): (2, False),
    ("Hot Air Skyway", 4): (2, False), ("Hot Air Skyway", 5): (2, False), ("Hot Air Skyway", 6): (2, False),
    ("Hot Air Skyway", 7): (2, False), ("Hot Air Skyway", 8): (2, True), ("Hot Air Skyway", 9): (2, False),
    ("Hot Air Skyway", 13): (2, False), ("Hot Air Skyway", 14): (2, False), ("Hot Air Skyway", 15): (2, False),
    ("Tiny Arena", 1): (1, False),
}

BOOST_TEXT = {
    1: "With Progressive Boost on: 1 Progressive Boost (boost).",
    2: "With Progressive Boost on: 2 Progressive Boost (Ultimate Sacred Fire).",
}
STATS_TEXT = "With Progressive Stats on: one Top Speed, one Acceleration and one Turning upgrade."
DOOR_TEXT = (
    "With Itemsanity on: a weapon that breaks the stone door: Bomb, Missile, "
    "Beaker, Shield Bubble or Mask, or a x3 version."
)


def _requirements(name: str, number: int) -> list[str]:
    boost, stats = BOX_RULES.get((name, number), (0, False))
    out = []
    if boost:
        out.append(BOOST_TEXT[boost])
    if stats:
        out.append(STATS_TEXT)
    if (name, number) == ("Tiger Temple", 5):
        out.append(DOOR_TEXT)
    return out


# Written for pictures where the surroundings alone are hard to recognise.
HINTS: dict[tuple[str, int], str] = {
    ("Oxide Station", 11): "Floats in open space just above the edge of the platform right after the tunnel exit.",
    ("N. Gin Labs", 7): "On the corridor floor just before the doorway with the yellow arrow sign.",
    ("Dragon Mines", 10): "Against the cave wall on the purple rock stretch, between Item Box 9 and Item Box 11.",
    ("Sewer Speedway", 10): "Inside the red pipe, in the middle of the road.",
    ("Cortex Castle", 6): "On the walkway along the outside of the castle wall.",
    ("Cortex Castle", 7): "On the walkway along the outside of the castle wall.",
    ("Cortex Castle", 8): "On the walkway along the outside of the castle wall.",
    ("Cortex Castle", 9): "On the walkway along the outside of the castle wall.",
    ("Crash Cove", 7): "Floats in the air next to the bow of the pirate ship, over the water.",
    ("Tiger Temple", 5): "In the shortcut tunnel behind the breakable stone door, at the far end where it opens back up to the outside.",
    ("Hot Air Skyway", 8): "On the shortcut route. You can only reach it by taking the shortcut.",
    ("Tiger Temple", 10): "On the path at the corner of the temple wall.",
    ("Hot Air Skyway", 5): "Floats in open air just past the end of the road piece, next to the small blue balloon.",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(src_dir: Path) -> int:
    rows = list(csv.DictReader((src_dir / "manifest.csv").open(encoding="utf-8")))
    previous: dict[str, str] = {}
    if DATA_FILE.is_file():
        for track in json.loads(DATA_FILE.read_text(encoding="utf-8"))["tracks"]:
            for box in track["boxes"]:
                previous[box["full"]] = box["source_sha256"]

    by_track: dict[str, list[dict]] = {}
    for row in rows:
        by_track.setdefault(row["track"], []).append(row)

    hub_of = {name: hub for hub, names in HUBS for name in names}
    missing = set(by_track) ^ set(hub_of)
    if missing:
        raise SystemExit(f"track list mismatch between manifest and HUBS: {sorted(missing)}")

    written = 0
    tracks = []
    for hub, names in HUBS:
        for name in names:
            boxes = []
            slug = Path(by_track[name][0]["file"]).parts[0]
            out_dir = IMG_DIR / slug
            out_dir.mkdir(parents=True, exist_ok=True)
            for row in sorted(by_track[name], key=lambda r: int(r["box"])):
                number = int(row["box"])
                src = src_dir / row["file"]
                digest = _sha256(src)
                full = f"/img/ctr/ap-boxes/{slug}/box-{number:02d}.webp"
                thumb = f"/img/ctr/ap-boxes/{slug}/box-{number:02d}-thumb.webp"
                full_path = out_dir / f"box-{number:02d}.webp"
                thumb_path = out_dir / f"box-{number:02d}-thumb.webp"
                if previous.get(full) != digest or not full_path.is_file() or not thumb_path.is_file():
                    image = Image.open(src).convert("RGB")
                    image.save(full_path, "WEBP", quality=FULL_QUALITY, method=6)
                    image.resize(THUMB_SIZE, Image.LANCZOS).save(
                        thumb_path, "WEBP", quality=THUMB_QUALITY, method=6
                    )
                    written += 1
                boxes.append(
                    {
                        "number": number,
                        "name": row["location_name"],
                        "full": full,
                        "thumb": thumb,
                        "shortcut_knowledge": SHORTCUT_KNOWLEDGE.get((name, number)),
                        "hint": HINTS.get((name, number)),
                        "requirements": _requirements(name, number),
                        "source_sha256": digest,
                    }
                )
            map_src = src_dir / slug / f"{slug}-map.svg"
            if map_src.is_file():
                MAP_DIR.mkdir(parents=True, exist_ok=True)
                (MAP_DIR / f"{slug}.svg").write_bytes(map_src.read_bytes())
            tracks.append(
                {"name": name, "slug": slug, "hub": hub, "map": map_src.is_file(), "boxes": boxes}
            )

    DATA_FILE.write_text(json.dumps({"tracks": tracks}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    total = sum(len(t["boxes"]) for t in tracks)
    print(f"{len(tracks)} tracks, {total} boxes, {written} pictures written")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    sys.exit(main(Path(sys.argv[1])))
