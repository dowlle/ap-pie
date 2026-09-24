"""Render the 1200x630 social preview cards for the CTR AP box pages.

One card per track (track map, name, box count and one box picture) and one
for the index (a collage of box pictures). Reads ap-boxes.json, the inline map
SVGs and the imported WebP pictures, and screenshots an HTML card with headless
Chromium. Output: ap-web/frontend/public/img/ctr/ap-boxes/og/<slug>.jpg and
index.jpg. Run it after scripts/import_ctr_ap_boxes.py whenever pictures or
maps change.

Usage:
    python scripts/render_ctr_ap_box_og.py --chrome /path/to/chrome
"""

from __future__ import annotations

import argparse
import base64
import html
import io
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "ap-web" / "frontend" / "public"
DATA_FILE = ROOT / "ap-web" / "guides" / "ctr-reference" / "ap-boxes.json"
MAP_DIR = ROOT / "ap-web" / "templates" / "ctr" / "ap-box-maps"
OUT_DIR = PUBLIC / "img" / "ctr" / "ap-boxes" / "og"

# Index collage: one recognisable box from six different tracks.
INDEX_PICKS = [
    ("mystery-caves", 13), ("hot-air-skyway", 10), ("papus-pyramid", 7),
    ("n-gin-labs", 13), ("polar-pass", 8), ("coco-park", 3),
]

STYLE = """
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,700&family=Inter+Tight:wght@500;600&display=swap');
* { box-sizing: border-box; margin: 0; }
html, body { width: 1200px; height: 630px; overflow: hidden; background: #121016; }
body { font-family: 'Inter Tight', Arial, sans-serif; color: #f5f1eb; }
.card { position: relative; width: 1200px; height: 630px; display: flex; }
.map { width: 560px; height: 630px; padding: 28px; display: flex; align-items: center; justify-content: center; background: #1b181f; }
.map svg { width: 100%; height: 100%; }
.text { flex: 1; padding: 52px 56px 44px 48px; display: flex; flex-direction: column; }
.kicker { color: #f2ad55; font-weight: 600; font-size: 24px; letter-spacing: 0.02em; }
h1 { font-family: 'Bricolage Grotesque', Arial, sans-serif; font-weight: 700; font-size: 60px; line-height: 1.02; margin: 14px 0 12px; }
.sub { color: #a59c91; font-size: 28px; font-weight: 500; }
.pic { margin-top: auto; width: 100%; aspect-ratio: 16 / 9; border-radius: 14px; border: 2px solid #332d39; object-fit: cover; }
.site { position: absolute; right: 56px; top: 56px; color: #746d68; font-size: 22px; font-weight: 600; }
.grid { width: 640px; height: 630px; display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: repeat(3, 1fr); gap: 6px; padding: 6px; background: #1b181f; }
.grid img { width: 100%; height: 100%; object-fit: cover; border-radius: 6px; }
.index .text { padding-top: 70px; }
.index h1 { font-size: 64px; }
.index .sub { margin-top: 6px; line-height: 1.35; }
.index .site { position: static; margin-top: auto; }
"""


def _data_uri(path: Path, crop_caption: bool = False) -> str:
    if not crop_caption:
        return "data:image/webp;base64," + base64.b64encode(path.read_bytes()).decode()
    # Drop the 48px caption strip at the bottom of the 1280x720 picture.
    image = Image.open(path).convert("RGB")
    image = image.crop((0, 0, image.width, image.height - image.height * 48 // 720))
    buffer = io.BytesIO()
    image.save(buffer, "WEBP", quality=85)
    return "data:image/webp;base64," + base64.b64encode(buffer.getvalue()).decode()


def _picture(web_path: str) -> Path:
    return PUBLIC / web_path.lstrip("/")


def _track_html(track: dict) -> str:
    svg = (MAP_DIR / f"{track['slug']}.svg").read_text(encoding="utf-8")
    count = len(track["boxes"])
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{STYLE}</style></head><body>
<div class="card">
  <div class="map">{svg}</div>
  <div class="text">
    <div class="kicker">CTR Archipelago</div>
    <h1>{html.escape(track['name'])}</h1>
    <div class="sub">{count} AP box locations, with a map and a picture of every box</div>
    <img class="pic" src="{_data_uri(_picture(track['boxes'][0]['full']))}">
  </div>
  <div class="site">ap-pie.com</div>
</div></body></html>"""


def _index_html(tracks: list[dict], total: int) -> str:
    by_slug = {t["slug"]: t for t in tracks}
    imgs = "".join(
        f'<img src="{_data_uri(_picture(by_slug[slug]["boxes"][n - 1]["full"]), crop_caption=True)}">'
        for slug, n in INDEX_PICKS
    )
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{STYLE}</style></head><body>
<div class="card index">
  <div class="grid">{imgs}</div>
  <div class="text">
    <div class="kicker">CTR Archipelago</div>
    <h1>AP box locations</h1>
    <div class="sub">All {total} AP item boxes on {len(tracks)} tracks, with a map and a picture of every box.</div>
    <div class="site">ap-pie.com</div>
  </div>
</div></body></html>"""


def _render(chrome: str, page: str, out: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "card.html"
        png = Path(tmp) / "card.png"
        src.write_text(page, encoding="utf-8")
        subprocess.run(
            [chrome, "--headless=new", "--no-sandbox", "--hide-scrollbars",
             "--window-size=1200,630", "--virtual-time-budget=8000",
             f"--screenshot={png}", src.as_uri()],
            check=True, capture_output=True,
        )
        Image.open(png).convert("RGB").crop((0, 0, 1200, 630)).save(
            out, "JPEG", quality=85, optimize=True, progressive=True
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chrome", required=True)
    args = parser.parse_args()
    tracks = json.loads(DATA_FILE.read_text(encoding="utf-8"))["tracks"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for track in tracks:
        _render(args.chrome, _track_html(track), OUT_DIR / f"{track['slug']}.jpg")
    total = sum(len(t["boxes"]) for t in tracks)
    _render(args.chrome, _index_html(tracks, total), OUT_DIR / "index.jpg")
    print(f"{len(tracks) + 1} cards written to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
