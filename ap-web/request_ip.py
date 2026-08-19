"""Resolve a client address without trusting caller-controlled headers."""

from __future__ import annotations

import ipaddress

from flask import request

import config


def client_ip() -> str:
    """Return Cloudflare's address only after the origin trust gate is active.

    Caddy overwrites ``X-AP-Origin-Verified`` on upstream requests. Operators
    must leave the feature disabled until Authenticated Origin Pulls is
    required, so a partial deployment collapses limits onto the socket peer
    rather than accepting an attacker-supplied address.
    """
    peer = request.remote_addr or "unknown"
    if not config.TRUST_CLOUDFLARE_HEADERS:
        return peer
    if request.headers.get("X-AP-Origin-Verified") != "cloudflare":
        return peer
    raw = request.headers.get("CF-Connecting-IP", "").strip()
    try:
        return str(ipaddress.ip_address(raw))
    except ValueError:
        return peer
