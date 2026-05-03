from __future__ import annotations

import atexit
import threading
from pathlib import Path

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

import config
from ap_lib import GameRecord, scan_output_dir
from auth import apply_auth_to_app
from server_manager import ServerManager

_records: list[GameRecord] = []
_records_lock = threading.RLock()
_records_file_count: int = 0

DIST_DIR = Path(__file__).parent / "frontend" / "dist"
STATE_DIR = Path(__file__).parent / ".state"


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
    # SEC-03: fail closed if SECRET_KEY is missing or still the default. The
    # default short-circuits to a known, public value which makes session
    # cookies forgeable by anyone who can read the source. Don't let the app
    # boot in that state - clearer than letting it serve traffic with a
    # broken trust model.
    if not config.SECRET_KEY or config.SECRET_KEY == "change-me-in-production":
        raise RuntimeError(
            "SECRET_KEY env var is missing or still the placeholder default. "
            "Generate one with `python3 -c 'import secrets; print(secrets.token_hex(32))'` "
            "and set it in the runtime environment before starting the app."
        )
    app.secret_key = config.SECRET_KEY
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    if config.DISCORD_REDIRECT_URI.startswith("https://"):
        app.config["SESSION_COOKIE_SECURE"] = True
    CORS(app, origins=config.CORS_ORIGINS.split(","), supports_credentials=True)
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
    from db import init_db
    db_available = False
    try:
        init_db(config.DATABASE_URL)
        db_available = True
    except Exception as e:
        app.logger.warning(f"Database not available: {e}. Market features will not work.")

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

    app.register_blueprint(games_bp)
    app.register_blueprint(summary_bp)
    app.register_blueprint(server_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(apworlds_bp)
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
        return send_from_directory(DIST_DIR, "index.html")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=config.DEBUG, port=5001)
