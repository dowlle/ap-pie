"""Home Assistant push for the registry (new submission, Saphi change, report).

AP-Pie has no Home Assistant client yet: the FEAT-37 hook is still backlog and
the push token lives on Atlas, not in the web tier. This is the stub for it.
With nothing configured it only logs; with AP_CTR_REGISTRY_HA_URL and
AP_CTR_REGISTRY_HA_TOKEN set (a Home Assistant notify service URL and a
long-lived token, from the environment) it posts a short message.

It never raises: a failed push must not fail a submission. The message holds a
title and a count, never a user name or a submitted descriptor.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request

log = logging.getLogger("ctr_registry.notify")


def push(title: str, message: str) -> bool:
    url = os.environ.get("AP_CTR_REGISTRY_HA_URL", "")
    token = os.environ.get("AP_CTR_REGISTRY_HA_TOKEN", "")
    if not url or not token or not url.startswith("https://"):
        log.info("registry push (not configured): %s - %s", title, message)
        return False
    body = json.dumps({"title": title[:80], "message": message[:300]}).encode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5):  # noqa: S310 (https enforced above)
            return True
    except Exception as exc:  # noqa: BLE001
        log.warning("registry push failed: %s", type(exc).__name__)
        return False
