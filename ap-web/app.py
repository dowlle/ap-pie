from __future__ import annotations

import atexit
import html
import json
import re
import threading
from pathlib import Path

from flask import Flask, Response, g, jsonify, send_from_directory
from flask_cors import CORS

import config
import seo
from ap_lib import GameRecord, scan_output_dir
from auth import apply_auth_to_app
from server_manager import ServerManager

_records: list[GameRecord] = []
_records_lock = threading.RLock()
_records_file_count: int = 0

DIST_DIR = Path(__file__).parent / "frontend" / "dist"
STATE_DIR = Path(__file__).parent / ".state"

SPA_STATIC_PATHS = {
    "", "market", "admin", "admin/apworld-requests", "rooms", "tracker",
    "servers", "apworlds", "yaml-builder", "rooms/templates", "my",
    "presets", "summary",
}
SPA_DYNAMIC_PATHS = (
    re.compile(r"(?:market|play|r|rooms|yaml-builder|my)/[^/]+"),
    re.compile(r"games/[^/]+(?:/market)?"),
)

PUBLIC_ROUTE_SEO = {
    "": {
        "title": "Archipelago Pie: Multiworld Randomizer Tools & Guides",
        "description": "Learn how Archipelago multiworld randomizers work, build player YAMLs, browse community APWorlds, and organize games with Archipelago Pie.",
        "canonical": "https://ap-pie.com/",
        "heading": "Your games, connected by one randomizer.",
        "intro": "Archipelago Pie helps beginners learn Archipelago, build player YAMLs, browse community game integrations, and organize multiworld sessions.",
        "schema_type": "WebPage",
    },
    "apworlds": {
        "title": "APWorld Downloads & YAML Builder | Archipelago Pie",
        "description": "Browse community Archipelago APWorlds by game and version, open setup resources, download integrations, and create compatible player YAMLs.",
        "canonical": "https://ap-pie.com/apworlds",
        "heading": "APWorld downloads and YAML builder",
        "intro": "An APWorld adds a game to Archipelago. Browse maintained community integrations, download the version your host expects, or create a compatible player YAML in the guided builder.",
        "schema_type": "CollectionPage",
    },
    "yaml-builder": {
        "title": "Archipelago YAML Builder | Archipelago Pie",
        "description": "Build an Archipelago player YAML from guided game options, review the generated file, and download it for your host or multiworld.",
        "canonical": "https://ap-pie.com/yaml-builder",
        "heading": "Build an Archipelago player YAML",
        "intro": "Choose a supported game, configure its options in a guided form, review the generated YAML, and download a player file ready to share with your host.",
        "schema_type": "WebPage",
    },
}


def _public_spa_response(path: str) -> Response:
    """Serve meaningful route-specific HTML before React takes over."""
    route = PUBLIC_ROUTE_SEO[path]
    document = (DIST_DIR / "index.html").read_text(encoding="utf-8")
    title = html.escape(route["title"])
    description = html.escape(route["description"], quote=True)
    canonical = html.escape(route["canonical"], quote=True)
    document = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", document, count=1)
    document = re.sub(
        r'<meta name="description" content="[^"]*"\s*/>',
        f'<meta name="description" content="{description}" />',
        document,
        count=1,
    )
    document = re.sub(
        r'<meta property="og:title" content="[^"]*"\s*/>',
        f'<meta property="og:title" content="{title}" />',
        document,
        count=1,
    )
    document = re.sub(
        r'<meta property="og:description" content="[^"]*"\s*/>',
        f'<meta property="og:description" content="{description}" />',
        document,
        count=1,
    )
    page_node = seo.page(
        config.PUBLIC_BASE_URL,
        route["schema_type"],
        route["canonical"],
        route["title"],
        route["description"],
    )
    nodes = [page_node]
    if path == "yaml-builder":
        application_id = f'{route["canonical"]}#application'
        page_node["mainEntity"] = {"@id": application_id}
        nodes.append({
            "@type": "WebApplication",
            "@id": application_id,
            "name": route["title"],
            "url": route["canonical"],
            "description": route["description"],
            "applicationCategory": "UtilitiesApplication",
            "operatingSystem": "Any operating system with a web browser",
            "isPartOf": {"@id": seo.website_id(config.PUBLIC_BASE_URL)},
            "publisher": {"@id": seo.organization_id(config.PUBLIC_BASE_URL)},
        })
    structured = seo.graph(config.PUBLIC_BASE_URL, *nodes)
    route_meta = (
        f'<link rel="canonical" href="{canonical}" />\n'
        f'    <meta property="og:url" content="{canonical}" />\n'
        f'    <script type="application/ld+json">'
        f'{json.dumps(structured, separators=(",", ":")).replace("<", "\\u003c")}'
        f'</script>'
    )
    fallback = (
        '<main class="route-html-fallback">'
        f'<h1>{html.escape(route["heading"])}</h1>'
        f'<p>{html.escape(route["intro"])}</p>'
        '</main>'
    )
    document = document.replace("<!-- ROUTE_META -->", route_meta)
    document = document.replace("<!-- ROUTE_CONTENT -->", fallback)
    return Response(document, mimetype="text/html")


def _is_spa_route(path: str) -> bool:
    """Keep direct links working while giving genuinely unknown URLs a 404."""
    normalized = path.strip("/")
    return normalized in SPA_STATIC_PATHS or any(
        pattern.fullmatch(normalized) for pattern in SPA_DYNAMIC_PATHS
    )


def _output_file_count() -> int:
    """Count zip files in output dir to detect new games."""
    try:
        return sum(1 for f in Path(config.OUTPUT_DIR).iterdir()
                   if f.suffix == ".zip" and f.name.startswith("AP_"))
    except OSError:
        return 0


def get_records() -> list[GameRecord]:
    global _records, _records_file_count
    with _records_lock:
        current_count = _output_file_count()
        if not _records or current_count != _records_file_count:
            _records = scan_output_dir(Path(config.OUTPUT_DIR))
            _records_file_count = current_count
        return list(_records)


def _refresh_records() -> list[GameRecord]:
    global _records
    with _records_lock:
        _records = scan_output_dir(Path(config.OUTPUT_DIR))
        return list(_records)


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    # Audit-2026-05-04 #1: fail closed on insecure defaults at startup.
    # SECRET_KEY: a missing/placeholder value would make session cookies
    # forgeable by anyone who can read the source.
    # CORS_ORIGINS: empty or "*" combined with supports_credentials=True
    # would let any site read authenticated responses. flask-cors reflects
    # the request Origin under wildcard + credentials, which is exactly the
    # CORS misconfig the spec warns against.
    if not config.SECRET_KEY or config.SECRET_KEY == "change-me-in-production":
        raise RuntimeError(
            "SECRET_KEY env var is missing or still the placeholder default. "
            "Generate one with `python3 -c 'import secrets; print(secrets.token_hex(32))'` "
            "and set it in the runtime environment before starting the app."
        )
    cors_origins = [o.strip() for o in config.CORS_ORIGINS.split(",") if o.strip()]
    if not cors_origins or "*" in cors_origins:
        raise RuntimeError(
            "AP_CORS_ORIGINS env var is missing or contains '*'. "
            "supports_credentials is True, so a wildcard would expose "
            "authenticated responses to any origin. Set AP_CORS_ORIGINS "
            "to an explicit comma-separated list (e.g. https://ap-pie.com)."
        )
    app.secret_key = config.SECRET_KEY
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    if config.DISCORD_REDIRECT_URI.startswith("https://"):
        app.config["SESSION_COOKIE_SECURE"] = True
    # APIE-1: opt-in ap-pie-wide SSO. Both default to empty -> Flask keeps the
    # host-only cookie named "session" (unchanged for single-host deploys).
    # Ecosystem deploys set Domain=.ap-pie.com + Name=apie_session; beta sets
    # a distinct name + no domain so it stays isolated. See config.py.
    if config.SESSION_COOKIE_DOMAIN:
        app.config["SESSION_COOKIE_DOMAIN"] = config.SESSION_COOKIE_DOMAIN
    if config.SESSION_COOKIE_NAME:
        app.config["SESSION_COOKIE_NAME"] = config.SESSION_COOKIE_NAME
    CORS(app, origins=cors_origins, supports_credentials=True)

    @app.after_request
    def _security_headers(response: Response) -> Response:
        """SEC-30/35: baseline browser isolation for every response."""
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
            "form-action 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self' wss:; "
            "frame-src https://www.youtube-nocookie.com; "
            "upgrade-insecure-requests",
        )
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        )
        return response

    app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024
    app.config["AP_HOST"] = config.HOST
    app.config["AP_WORLDS_DIR"] = config.WORLDS_DIR
    app.config["AP_INDEX_DIR"] = str(STATE_DIR / "archipelago-index")
    app.config["AP_INDEX_REPO"] = config.INDEX_REPO

    # Server manager
    STATE_DIR.mkdir(exist_ok=True)

    def _on_server_stopped(seed: str) -> None:
        """Update room status when a server stops or crashes."""
        try:
            from db import _db_url
            if _db_url is None:
                return
            from db import list_rooms, update_room, add_activity
            rooms = list_rooms()
            for r in rooms:
                if r.get("seed") == seed and r.get("status") == "playing":
                    update_room(r["id"], status="generated")
                    add_activity(r["id"], "server", "Server stopped (process exited)")
        except Exception as e:
            app.logger.error(f"Failed to update room status for seed {seed}: {e}")

    manager = ServerManager(
        server_exe=config.SERVER_EXE,
        host=config.HOST,
        port_start=config.PORT_RANGE_START,
        port_end=config.PORT_RANGE_END,
        state_file=str(STATE_DIR / "servers.json"),
        on_server_stopped=_on_server_stopped,
    )
    app.config["server_manager"] = manager
    atexit.register(manager.shutdown)

    # Database
    from db import init_db, scrub_db_url
    db_available = False
    try:
        init_db(config.DATABASE_URL)
        db_available = True
    except Exception as e:
        # SEC-22: psycopg2's OperationalError text echoes the DSN with the
        # password embedded; scrub before logging so credentials don't leak
        # to gunicorn / Caddy access logs.
        app.logger.warning(f"Database not available: {scrub_db_url(e)}. Market features will not work.")

    # FEAT-04: background sweeper that auto-closes rooms whose submit_deadline
    # has passed. Runs every DEADLINE_SWEEP_INTERVAL_SECONDS in a daemon
    # thread so it dies with the worker. Lazy checks in the request path
    # cover deadline transitions between sweep ticks.
    if db_available:
        import time

        DEADLINE_SWEEP_INTERVAL_SECONDS = 60

        def _deadline_sweeper() -> None:
            from db import auto_close_expired_rooms, add_activity
            while True:
                try:
                    closed = auto_close_expired_rooms()
                    for room in closed:
                        try:
                            add_activity(
                                room["id"],
                                "room_closed",
                                f"Room auto-closed at scheduled deadline ({room['submit_deadline']})",
                            )
                        except Exception as ee:
                            app.logger.error(f"deadline sweeper: failed to log activity for {room['id']}: {ee}")
                except Exception as e:
                    app.logger.error(f"deadline sweeper tick failed: {e}")
                time.sleep(DEADLINE_SWEEP_INTERVAL_SECONDS)

        sweeper = threading.Thread(target=_deadline_sweeper, name="deadline-sweeper", daemon=True)
        sweeper.start()

    # FEAT-31: analytics recorder + retention sweeper.
    #
    # The recorder writes on a daemon thread so no user request ever waits on
    # an analytics INSERT. The sweeper folds each day into the counts-only
    # events_daily rollup and then prunes raw rows past the retention horizon
    # (GDPR Art. 5(1)(e)) - in-process rather than a host cron so it survives
    # redeploys and needs no state on the box.
    import analytics

    analytics.set_logger(app.logger)
    if db_available and config.ANALYTICS_ENABLED:
        analytics.start_writer()

        import os
        import time as _time

        RETENTION_SWEEP_INTERVAL_SECONDS = 12 * 3600

        def _retention_sweeper() -> None:
            from db import rollup_and_prune_events

            # Stagger workers so N gunicorn processes don't all sweep at once.
            _time.sleep(300 + (os.getpid() % 120))
            while True:
                try:
                    result = rollup_and_prune_events(config.ANALYTICS_RETENTION_DAYS)
                    if result["rows_pruned"]:
                        app.logger.info(
                            f"analytics retention: pruned {result['rows_pruned']} row(s) "
                            f"older than {config.ANALYTICS_RETENTION_DAYS} days"
                        )
                except Exception as e:
                    app.logger.error(f"analytics retention sweep failed: {e}")
                _time.sleep(RETENTION_SWEEP_INTERVAL_SECONDS)

        threading.Thread(
            target=_retention_sweeper, name="analytics-retention", daemon=True
        ).start()

    @app.before_request
    def _assign_request_id() -> None:
        """Correlation id for this request. Lets a client-posted event and the
        server-side event it triggered be lined up without any visitor
        identifier. Registered before the auth middleware so 403 recorders
        can read it."""
        g.request_id = analytics.new_request_id()

    # FEAT-17 V0: real-time WebSocket tracker. Off by default until V1
    # wires the cache into the API. Toggle with AP_TRACKER_WS_ENABLED=1.
    if db_available and config.TRACKER_WS_ENABLED:
        try:
            from tracker_ws import manager as tracker_ws_manager, bootstrap_from_db as tracker_ws_bootstrap
            tracker_ws_manager.start()
            atexit.register(tracker_ws_manager.stop)
            # Run bootstrap in a small daemon thread so app startup
            # doesn't block on the SELECT (and so any per-room scrape
            # fallback for slot-name discovery doesn't block startup).
            def _bootstrap() -> None:
                try:
                    n = tracker_ws_bootstrap()
                    app.logger.info(f"FEAT-17 bootstrap scheduled {n} connection(s)")
                except Exception as e:
                    app.logger.warning(f"FEAT-17 bootstrap failed: {e}")
            threading.Thread(target=_bootstrap, name="tracker-ws-bootstrap", daemon=True).start()
        except Exception as e:
            app.logger.warning(f"FEAT-17 tracker_ws init failed: {e}")

    from api.games import bp as games_bp
    from api.summary import bp as summary_bp
    from api.server import bp as server_bp
    from api.upload import bp as upload_bp
    from api.apworlds import bp as apworlds_bp
    from api.apworld_requests import bp as apworld_requests_bp
    from api.market import bp as market_bp
    from api.rooms import bp as rooms_bp
    from api.auth_routes import bp as auth_bp
    from api.templates import bp as templates_bp
    from api.admin import bp as admin_bp
    from api.health import bp as health_bp
    from api.connect import bp as connect_bp
    from api.submit import bp as submit_bp
    from api.public import bp as public_bp
    from api.features import bp as features_bp
    from api.deployment import bp as deployment_bp
    from api.room_templates import bp as room_templates_bp
    from api.guides import bp as guides_bp
    from api.ctr import bp as ctr_bp
    from api.events import bp as events_bp
    from api.presets import bp as presets_bp
    from api.user_yamls import bp as user_yamls_bp
    from api.legal import bp as legal_bp

    app.register_blueprint(games_bp)
    app.register_blueprint(summary_bp)
    app.register_blueprint(server_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(apworlds_bp)
    app.register_blueprint(apworld_requests_bp)
    app.register_blueprint(market_bp)
    app.register_blueprint(rooms_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(templates_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(connect_bp)
    app.register_blueprint(submit_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(features_bp)
    app.register_blueprint(deployment_bp)
    app.register_blueprint(room_templates_bp)
    # FEAT-39: server-rendered guide pages + sitemap. Registered before the
    # SPA catch-all below so /guides, /guides/<slug>, and /sitemap.xml resolve
    # to full server-rendered HTML instead of the client-side router.
    app.register_blueprint(guides_bp)
    # FEAT-40: server-rendered CTR section (/ctr, /ctr/download + stable
    # download redirects). Same before-the-catch-all rule as guides.
    app.register_blueprint(ctr_bp)
    # FEAT-31: analytics event intake + admin read surface, and the
    # server-rendered /privacy page that documents what they record.
    app.register_blueprint(events_bp)
    # FEAT-42: community presets for the YAML builder.
    app.register_blueprint(presets_bp)
    # FEAT-43: the player's own YAML library and submission history.
    app.register_blueprint(user_yamls_bp)
    app.register_blueprint(legal_bp)

    # Apply auth middleware - protects all /api/* except /api/market, /api/auth, /api/trackers
    apply_auth_to_app(app)

    @app.route("/api/refresh", methods=["POST"])
    def refresh():
        records = _refresh_records()
        return jsonify({"status": "ok", "count": len(records)})

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path: str):
        if path and (DIST_DIR / path).is_file():
            return send_from_directory(DIST_DIR, path)
        # A miss in the server-owned API namespace must remain an API-shaped
        # 404. Returning the SPA document here confuses clients and produced
        # indexable-looking HTML for malformed download URLs.
        if path == "api" or path.startswith("api/"):
            return jsonify({"error": "API endpoint not found"}), 404
        normalized = path.strip("/")
        if normalized in PUBLIC_ROUTE_SEO:
            return _public_spa_response(normalized)
        response = send_from_directory(DIST_DIR, "index.html")
        if not _is_spa_route(path):
            response.status_code = 404
        return response

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=config.DEBUG, port=5001)
