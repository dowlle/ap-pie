"""FEAT-40: server-rendered CTR Archipelago section.

Same pattern as api/guides.py: these routes are NOT part of the React SPA.
They render full HTML on the server so search engines and AI answer systems
get complete content, a real <title>, meta description, canonical URL, and
Open Graph tags without executing any JavaScript. The blueprint is registered
before the SPA catch-all in app.py, so these paths win over the client-side
router.

The download routes exist so that tutorials, video descriptions, and Discord
pins can link a stable URL (/ctr/download/windows) that never goes stale:
the redirect target moves to the new artifact when a release ships, the
public URL does not.
"""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, abort, redirect, render_template

import config

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

bp = Blueprint("ctr", __name__, template_folder=str(_TEMPLATES_DIR))


_RELEASE_BASE = "https://github.com/dowlle/ctr-native-ap/releases/download"

# The stable channel. Updating this dict is a manual step on the CTR release
# checklist: bump version/released and point the asset URLs at the new GitHub
# Release. The visible page version and the redirect targets both read from
# here so they cannot drift apart.
STABLE: dict = {
    "version": "0.1.5",
    "released": "2026-08-06",
    "downloads": {
        "windows": f"{_RELEASE_BASE}/v0.1.5/ctr-archipelago-v0.1.5-windows-x86.zip",
        "linux": f"{_RELEASE_BASE}/v0.1.5/ctr-archipelago-v0.1.5-linux-x86.tar.gz",
        "apworld": f"{_RELEASE_BASE}/v0.1.5/ctr.apworld",
    },
}

# The testing channel. None hides the testing card on /ctr/download. When a
# pre-release tag exists on GitHub, set this to e.g.
#   {"version": "0.2.0-pre1", "url": "https://github.com/dowlle/ctr-native-ap/releases/tag/v0.2.0-pre1"}
# and the card renders with the client/seed compatibility warning. Testing
# builds deliberately get no stable redirect aliases: stable URLs are for
# tutorials, and tutorials only ever reference the stable channel.
PRERELEASE: dict | None = None

# Bump when page content materially changes; feeds the sitemap lastmod.
PAGES_UPDATED = "2026-08-16"

# Consumed by api/guides.py for /sitemap.xml and /llms.txt so the CTR section
# never goes stale in either surface separately.
CTR_PAGES: list[dict] = [
    {
        "path": "/ctr",
        "title": "CTR Archipelago",
        "blurb": "Crash Team Racing as a native Archipelago randomizer, no emulator involved.",
    },
    {
        "path": "/ctr/download",
        "title": "Download CTR Archipelago",
        "blurb": "Current stable CTR Archipelago downloads for Windows and Linux.",
    },
]


def _canonical(path: str) -> str:
    return f"{config.PUBLIC_BASE_URL}{path}"


@bp.route("/ctr", strict_slashes=False)
def ctr_landing() -> str:
    return render_template(
        "ctr/landing.html",
        stable=STABLE,
        page_title="CTR Archipelago, the Crash Team Racing randomizer | Archipelago Pie",
        meta_description=(
            "Play Crash Team Racing as an Archipelago multiworld randomizer. "
            "Race for progression, send items between games, and play CTR "
            "natively on Windows, Linux, or Steam Deck. No emulator needed."
        ),
        canonical_url=_canonical("/ctr"),
        og_type="website",
        og_image=_canonical("/img/ctr/og-ctr.jpg"),
        site_url=_canonical("/"),
    )


@bp.route("/ctr/download", strict_slashes=False)
def ctr_download() -> str:
    return render_template(
        "ctr/download.html",
        stable=STABLE,
        prerelease=PRERELEASE,
        page_title="Download CTR Archipelago | Archipelago Pie",
        meta_description=(
            "Download the latest stable CTR Archipelago client for Windows or "
            "Linux and start playing Crash Team Racing in an Archipelago "
            "multiworld."
        ),
        canonical_url=_canonical("/ctr/download"),
        og_type="website",
        og_image=_canonical("/img/ctr/og-ctr.jpg"),
        site_url=_canonical("/"),
    )


@bp.route("/ctr/download/<platform>")
def ctr_download_redirect(platform: str):
    url = STABLE["downloads"].get(platform)
    if url is None:
        abort(404)
    return redirect(url, code=302)
