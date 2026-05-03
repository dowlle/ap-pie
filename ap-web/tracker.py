"""Fetch game/player data from an Archipelago tracker URL.

Supports archipelago.gg-style URLs (`/tracker/<room_id>`) only. We scrape
their `#checks-table` HTML - that gives us slot, name, game, connection
status, checks done/total, and completion %. Per-slot item lists and
hints are NOT on the main tracker page (they live behind extra fetches
to `/tracker/<id>/<slot>/<team>`), so Archipelago Pie doesn't surface them.

For richer dashboards the AP community uses cheese-trackers
(`cheesetrackers.theincrediblewheelofchee.se`) and anaptracker
(`anaptracker.tomagueri.fr`). Both run their own backend that polls the
AP server WebSocket directly and add slot claiming, BK/go-mode flags,
ping policies, etc. Adding fetchers for those richer sources is parked
at FEAT-14 in the Archipelago Pie devlog.
"""

from __future__ import annotations

import html as _html
import ipaddress
import logging
import re
import socket
import time
from collections import OrderedDict
from urllib.parse import urlparse

import requests

import config

logger = logging.getLogger(__name__)

# Shared per-room + per-slot cache. Ordered so LRU eviction is one
# popitem call when we hit TRACKER_CACHE_MAX. Reads call move_to_end so
# popular keys survive eviction.
_cache: "OrderedDict[str, tuple[float, dict]]" = OrderedDict()


def _cache_get(key: str, ttl: int) -> dict | None:
    """LRU read: returns the cached value if fresh, refreshing recency on hit."""
    entry = _cache.get(key)
    if entry is None:
        return None
    cached_time, cached_data = entry
    if time.time() - cached_time >= ttl:
        return None
    _cache.move_to_end(key)
    return cached_data


def _cache_set(key: str, value: dict) -> None:
    """LRU write: insert (or refresh) at the end and evict from the front
    if we're past the cap. Cap is read at insert time so a live env-var
    bump on the host takes effect on the next write without a restart."""
    _cache[key] = (time.time(), value)
    _cache.move_to_end(key)
    cap = max(1, config.TRACKER_CACHE_MAX)
    while len(_cache) > cap:
        _cache.popitem(last=False)


def _clean_cell(raw: str) -> str:
    """Strip HTML tags, decode entities (&amp; → &, &apos; → ', &#39; → '),
    normalise whitespace. Used by every per-cell parser so HTML-encoded
    player/item/location names render as readable text and - critically -
    match the plain-text values stored in `room_yamls` for FEAT-14 owner
    attribution. Without this, a YAML player named `W&G Fan_SM64` would
    arrive as `W&amp;G Fan_SM64` and never match the submitter row."""
    stripped = re.sub(r"<[^>]+>", "", raw)
    return _html.unescape(stripped).strip()

# Match tracker URLs like https://archipelago.gg/tracker/ABC123/0/...
_TRACKER_RE = re.compile(
    r"https?://(?P<host>[^/]+)/tracker/(?P<room_id>[^/]+)(?:/(?P<slot>\d+))?",
)

_SAFE_SCHEMES = frozenset({"http", "https"})


def _resolve_ips(host: str) -> list:
    """DNS-resolve host to a list of ipaddress objects. Empty on failure.

    Goes through the OS resolver via getaddrinfo, which normalises alt-encoded
    IPv4 literals (`0177.0.0.1` octal, `2130706433` decimal) into their
    canonical dotted-quad form. That's load-bearing: a string-prefix check
    on the raw host would miss those encodings even though the kernel still
    resolves them to 127.0.0.1.
    """
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError):
        return []
    out = []
    for info in infos:
        sockaddr = info[4]
        try:
            out.append(ipaddress.ip_address(sockaddr[0]))
        except (ValueError, IndexError):
            continue
    return out


def is_safe_outbound_host(host: str) -> bool:
    """Return True if `host` resolves to public, routable IP(s).

    Rejects loopback, RFC1918, link-local, multicast, reserved, unspecified,
    and CGNAT — `ipaddress.ip_address.is_global` is the inverse and covers
    them all. Resolves via DNS so encoded IPs (`0177.0.0.1`, `2130706433`,
    `[::ffff:127.0.0.1]`) and hostnames pointing at internal IPs are caught.

    Does NOT defend against DNS rebinding (host resolves to a public IP at
    validation time and to 127.0.0.1 at fetch time). The proper fix re-resolves
    at fetch time and connects to the IP literal — heavier change parked under
    SEC-03.

    Fails closed: if DNS resolution fails entirely, we return False rather
    than letting an unresolvable host slip through. Legitimate hosts with DNS
    issues will fail at fetch time anyway, so blocking at validation time is
    the safer default.
    """
    if not isinstance(host, str) or not host:
        return False
    cleaned = host.strip().lower().rstrip(".")
    if not cleaned:
        return False
    # Strip IPv6 brackets if present, e.g. "[::1]" -> "::1".
    if cleaned.startswith("[") and cleaned.endswith("]"):
        cleaned = cleaned[1:-1]
    ips = _resolve_ips(cleaned)
    if not ips:
        return False
    return all(ip.is_global for ip in ips)


def is_safe_tracker_url(url: str) -> bool:
    """Return True if `url` is a fetchable external HTTP(S) URL.

    Rejects non-http schemes (file, gopher, ftp, data, ...), missing
    hostnames, and any host that resolves to a non-global IP. SEC-03 closed:
    the IP-resolution check supersedes the earlier string-prefix loopback
    test, so alt encodings and RFC1918 are handled too.
    """
    if not isinstance(url, str) or not url:
        return False
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False
    if parsed.scheme not in _SAFE_SCHEMES:
        return False
    host = parsed.hostname or ""
    if not host:
        return False
    return is_safe_outbound_host(host)


def parse_tracker_url(url: str) -> dict | None:
    """Extract host and room_id from a tracker URL."""
    if not is_safe_tracker_url(url):
        return None
    m = _TRACKER_RE.match(url.strip())
    if not m:
        return None
    return {
        "host": m.group("host"),
        "room_id": m.group("room_id"),
        "slot": int(m.group("slot")) if m.group("slot") else None,
        "base_url": f"https://{m.group('host')}",
    }


def fetch_tracker_data(tracker_url: str, force: bool = False) -> dict:
    """Fetch tracker data from an archipelago.gg tracker URL.

    Strategy: HTML-first. archipelago.gg's `/api/tracker/<id>` JSON endpoint
    has rich per-slot data (item lists, hints, status ints) but doesn't
    include slot names + games - those live only on the HTML page. Since
    the LiveTracker UI needs name + game + checks + %, and HTML carries
    all four, we go straight to HTML.

    The richer JSON shape is left unparsed for now - see FEAT-14 for the
    parking spot if we want to layer item lists / hints in later.

    Results are cached for TRACKER_CACHE_TTL seconds via the shared LRU.
    """
    if not force:
        hit = _cache_get(tracker_url, config.TRACKER_CACHE_TTL)
        if hit is not None:
            return hit

    parsed = parse_tracker_url(tracker_url)
    if not parsed:
        return {"error": "Invalid tracker URL format"}

    return _fetch_tracker_html(tracker_url, parsed)


def _fetch_tracker_html(tracker_url: str, parsed: dict) -> dict:
    """Scrape tracker data from the HTML page as a fallback."""
    try:
        resp = requests.get(tracker_url.strip(), timeout=10)
        resp.raise_for_status()
        html = resp.text

        players = _parse_tracker_html(html)
        result = {
            "room_id": parsed["room_id"],
            "host": parsed["host"],
            "players": players,
            "player_count": len(players),
            "games": list({p["game"] for p in players if p.get("game")}),
        }
        _cache_set(tracker_url, result)
        return result

    except requests.RequestException as e:
        return {"error": f"Failed to fetch tracker: {e}"}


def _normalize_tracker_data(data: dict, parsed: dict) -> dict:
    """Normalize API response into our standard format."""
    players = []
    for slot_info in data.get("games", data.get("slots", [])):
        players.append({
            "slot": slot_info.get("slot", slot_info.get("team", 0)),
            "name": slot_info.get("name", slot_info.get("player", "")),
            "game": slot_info.get("game", ""),
            "checks_done": slot_info.get("checks_done", slot_info.get("checked_locations", 0)),
            "checks_total": slot_info.get("checks_total", slot_info.get("total_locations", 0)),
            "status": slot_info.get("status", 0),
        })

    return {
        "room_id": parsed["room_id"],
        "host": parsed["host"],
        "players": players,
        "player_count": len(players),
        "games": list({p["game"] for p in players if p.get("game")}),
    }


_AP_STATUS_TO_INT = {
    "disconnected": 0,
    "connected": 20,
    "ready": 5,
    "playing": 10,
    "goal completed": 30,
    "goal": 30,
}


def _parse_tracker_html(html: str) -> list[dict]:
    """Parse archipelago.gg's `#checks-table` rows for player data.

    Their tracker page is server-rendered HTML with a 7-column table:
    `# / Name / Game / Status / Checks (done/total) / % / LastActivity`.
    The table id is `checks-table`. We slice from there to the closing
    </table> and pull each row.

    Returns checks_done / checks_total / completion %, mapped to the same
    `players` shape `_normalize_tracker_data` produces. Status text gets
    mapped to AP client_status ints so the LiveTracker can render the right
    label colour. Per-slot item data isn't on the page - that only lives on
    /tracker/<id>/<slot>/<team> sub-pages and would need extra fetches.
    """
    table_start = html.find('id="checks-table"')
    if table_start < 0:
        return []
    table_end = html.find("</table>", table_start)
    table = html[table_start:table_end] if table_end > 0 else html[table_start:]

    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.DOTALL)
    players: list[dict] = []
    for row in rows:
        # Each row's <td> cells. center-column class is used on numeric cells;
        # plain <td> on the text cells. Tag-strip, decode HTML entities,
        # whitespace-normalise.
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(cells) < 5:
            continue
        clean = [_clean_cell(c) for c in cells]
        try:
            slot = int(clean[0])
        except ValueError:
            continue
        name = clean[1]
        game = clean[2]
        status_text = clean[3].lower()
        checks_text = clean[4]
        # checks cell looks like "0/48"; sometimes with surrounding whitespace.
        m = re.match(r"(\d+)\s*/\s*(\d+)", checks_text)
        if m:
            checks_done = int(m.group(1))
            checks_total = int(m.group(2))
        else:
            checks_done = 0
            checks_total = 0
        players.append({
            "slot": slot,
            "name": name,
            "game": game,
            "checks_done": checks_done,
            "checks_total": checks_total,
            "status": _AP_STATUS_TO_INT.get(status_text, 0),
        })
    return players


def clear_cache(tracker_url: str | None = None) -> None:
    """Clear cached tracker data."""
    if tracker_url:
        _cache.pop(tracker_url, None)
    else:
        _cache.clear()


# ---------------------------------------------------------------------------
# FEAT-14: per-slot detail page scraping.
#
# archipelago.gg renders a separate page per slot at
# /tracker/<room_id>/<team>/<slot> with three tables we care about:
#   - #received-table:  Item | Amount | Last Order Received
#   - #locations-table: Location | Checked (✔ or empty)
#   - #hints-table:     Finder | Receiver | Item | Location | Game | Entrance | Found
#
# Item and location names come pre-rendered on this page (no datapackage
# resolution needed). One fetch per modal open, cached server-side with the
# same TTL as the main tracker page.
# ---------------------------------------------------------------------------


def _slot_cache_key(tracker_url: str, team: int, slot: int) -> str:
    return f"{tracker_url}::slot/{team}/{slot}"


def _build_slot_url(tracker_url: str, team: int, slot: int) -> str | None:
    parsed = parse_tracker_url(tracker_url)
    if not parsed:
        return None
    return f"{parsed['base_url']}/tracker/{parsed['room_id']}/{team}/{slot}"


def _parse_slot_table(html: str, table_id: str, n_cols: int) -> list[list[str]]:
    """Slice out a table by id and return its <tbody> rows as cleaned cell lists.

    Mirrors the regex approach already used by `_parse_tracker_html` - no
    BeautifulSoup dependency.
    """
    start = html.find(f'id="{table_id}"')
    if start < 0:
        return []
    end = html.find("</table>", start)
    table = html[start:end] if end > 0 else html[start:]
    body_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", table, re.DOTALL)
    body = body_m.group(1) if body_m else table
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.DOTALL)
    out: list[list[str]] = []
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(cells) < n_cols:
            continue
        out.append([_clean_cell(c) for c in cells])
    return out


def _parse_received_table(html: str) -> list[dict]:
    rows = _parse_slot_table(html, "received-table", n_cols=3)
    items: list[dict] = []
    for cells in rows:
        try:
            amount = int(cells[1])
        except (ValueError, IndexError):
            amount = 0
        try:
            last_order = int(cells[2])
        except (ValueError, IndexError):
            last_order = 0
        items.append({
            "item": cells[0],
            "amount": amount,
            "last_order": last_order,
        })
    return items


def _parse_locations_table(html: str) -> list[dict]:
    rows = _parse_slot_table(html, "locations-table", n_cols=2)
    locs: list[dict] = []
    for cells in rows:
        # Checked column is "✔" when done, empty/whitespace otherwise.
        checked = bool(cells[1].strip())
        locs.append({
            "location": cells[0],
            "checked": checked,
        })
    return locs


def _parse_hints_table(html: str) -> list[dict]:
    rows = _parse_slot_table(html, "hints-table", n_cols=7)
    hints: list[dict] = []
    for cells in rows:
        # Found column is "✔" when item has been found, empty otherwise.
        found = bool(cells[6].strip())
        hints.append({
            "finder": cells[0],
            "receiver": cells[1],
            "item": cells[2],
            "location": cells[3],
            "game": cells[4],
            "entrance": cells[5],
            "found": found,
        })
    return hints


def _parse_slot_title(html: str) -> str | None:
    """Pull the slot's display name out of the <title> tag.

    archipelago.gg renders titles like "<SlotName>'s Tracker". Returns the
    SlotName portion, or None if the title doesn't match.
    """
    m = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
    if not m:
        return None
    # _html.unescape handles &apos;, &amp;, &#39;, etc. uniformly.
    title = _html.unescape(m.group(1)).strip()
    if title.lower().endswith("'s tracker"):
        return title[:-len("'s tracker")].strip()
    return title or None


def fetch_slot_data(
    tracker_url: str, team: int, slot: int, force: bool = False,
) -> dict:
    """FEAT-14: fetch per-slot detail (items / locations / hints) from
    archipelago.gg's /tracker/<id>/<team>/<slot> page.

    Returns a dict shaped like:
        {
          "team": int, "slot": int,
          "name": str | None,         # from <title>
          "items_received": [...],
          "locations": [...],
          "hints": [...],
          "tracker_url": str,         # for the "View on archipelago.gg" link
        }
    or {"error": "..."} on failure.

    Cached server-side via the shared LRU. Uses TRACKER_SLOT_CACHE_TTL
    (default 60s) - a longer window than the per-room grid because items
    received / locations checked / hints change less often than the
    rolling completion %, and the modal has a manual Refresh button as
    the user's escape hatch when they want fresh data.
    """
    if team < 0 or slot < 1:
        return {"error": "Invalid team or slot"}

    cache_key = _slot_cache_key(tracker_url, team, slot)
    if not force:
        hit = _cache_get(cache_key, config.TRACKER_SLOT_CACHE_TTL)
        if hit is not None:
            return hit

    slot_url = _build_slot_url(tracker_url, team, slot)
    if not slot_url:
        return {"error": "Invalid tracker URL format"}

    try:
        resp = requests.get(slot_url, timeout=10)
        resp.raise_for_status()
        body = resp.text
        # archipelago.gg returns 200 with an empty body when the slot doesn't
        # exist for the room (rare; treat as a not-found explicitly).
        if 'id="received-table"' not in body:
            return {"error": "Slot not found on tracker page"}
        result = {
            "team": team,
            "slot": slot,
            "name": _parse_slot_title(body),
            "items_received": _parse_received_table(body),
            "locations": _parse_locations_table(body),
            "hints": _parse_hints_table(body),
            "tracker_url": slot_url,
        }
        _cache_set(cache_key, result)
        return result
    except requests.RequestException as e:
        return {"error": f"Failed to fetch slot tracker: {e}"}
