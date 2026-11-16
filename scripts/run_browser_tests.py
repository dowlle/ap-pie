#!/usr/bin/env python3
"""Run Playwright against the built frontend, Flask and a disposable database."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
from urllib.parse import urlsplit
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/browser"


def main():
    database = os.environ.get("BROWSER_TEST_DATABASE_URL", "")
    if not database or urlsplit(database).hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("Set BROWSER_TEST_DATABASE_URL to a disposable local Postgres database.")
    if not (ROOT / "ap-web/frontend/dist/index.html").is_file():
        raise SystemExit("Build the frontend before running browser tests.")

    with tempfile.TemporaryDirectory(prefix="ap-pie-browser-") as directory:
        state = Path(directory)
        index = state / "archipelago-index"
        shutil.copytree(FIXTURES / "index", index / "index")
        shutil.copyfile(FIXTURES / "index.lock", index / "index.lock")
        # A real local clone exercises index history without a network dependency.
        origin = state / "fixture-origin"
        index.rename(origin)
        subprocess.run(["git", "init", "-q", str(origin)], check=True)
        subprocess.run(["git", "-C", str(origin), "add", "index", "index.lock"], check=True)
        subprocess.run([
            "git", "-C", str(origin), "-c", "user.name=dowlle",
            "-c", "user.email=58628796+dowlle@users.noreply.github.com",
            "commit", "-qm", "Browser index fixture",
        ], check=True, env={**os.environ, "GIT_AUTHOR_DATE": "2026-11-16T00:00:00Z", "GIT_COMMITTER_DATE": "2026-11-16T00:00:00Z"})
        subprocess.run(["git", "clone", "-q", "--no-hardlinks", str(origin), str(index)], check=True)

        os.environ.update({
            "DATABASE_URL": database,
            "SECRET_KEY": "browser-tests-only-session-key",
            "AP_CORS_ORIGINS": "http://127.0.0.1",
            "AP_PUBLIC_BASE_URL": "https://ap-pie.com",
            "AP_DEPLOYMENT_LABEL": "beta",
            "FEATURE_TIMBERBORN_SECTION": "false",
            "FEATURE_GENERATION": "false",
            "AP_INDEX_WARM": "0",
            "AP_INDEX_REPO": str(origin),
            "AP_OUTPUT_DIR": str(state / "output"),
            "AP_WORLDS_DIR": str(state / "worlds"),
            "AP_ACCOUNT_ERASURE_LEDGER": str(state / "erasure.jsonl"),
            "DISCORD_CLIENT_ID": "browser-fixture",
            "DISCORD_CLIENT_SECRET": "browser-fixture-only",
            "DISCORD_REDIRECT_URI": "http://127.0.0.1/api/auth/callback",
        })
        sys.path.insert(0, str(ROOT / "ap-web"))
        import app as application
        from db import set_builder_schema
        from werkzeug.serving import make_server

        application.STATE_DIR = state
        app = application.create_app()
        for path in sorted((FIXTURES / "schemas").glob("*.json")):
            record = json.loads(path.read_text())
            set_builder_schema(record["sha256"], record["apworld_name"], record["version"], record["schema"])

        # Any newly introduced cold-schema dependency must get a pinned fixture.
        with patch("api.apworlds._fetch_apworld_bytes", side_effect=AssertionError("Unpinned browser schema")):
            server = make_server("127.0.0.1", 0, app, threaded=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                result = subprocess.run(
                    ["npx", "playwright", "test", *sys.argv[1:], "--retries=0", "--forbid-only"],
                    cwd=ROOT / "ap-web/frontend",
                    env={**os.environ, "PLAYWRIGHT_BASE_URL": f"http://127.0.0.1:{server.server_port}"},
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
        return result.returncode


if __name__ == "__main__":
    sys.exit(main())
