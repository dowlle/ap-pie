"""Feature flag introspection + decorator for gating endpoints.

The flag map itself lives in config.FEATURES (env-driven). This module exposes
the current state to the frontend (so it can hide UI surfaces) and provides
the requires_feature decorator for backend routes.
"""

from __future__ import annotations

from functools import wraps

from flask import Blueprint, jsonify

import config

bp = Blueprint("features", __name__)


@bp.route("/api/features")
def get_features():
    """Public read of the current feature flag state.

    Frontend reads this once at boot via the FeaturesContext; safe to be public
    because the flag values are not secret - anyone could already infer them
    from which UI surfaces render.
    """
    return jsonify(dict(config.FEATURES))


def requires_feature(name: str):
    """Route decorator. Returns 403 with a structured payload when the named
    feature is disabled, so the frontend can react gracefully (e.g. show a
    'this feature is disabled' notice instead of a generic error).

    Usage:
        @bp.route("/api/foo", methods=["POST"])
        @requires_feature("generation")
        def create_foo(): ...
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not config.FEATURES.get(name, False):
                return jsonify({
                    "error": f"The '{name}' feature is currently disabled on this server.",
                    "feature": name,
                    "enabled": False,
                }), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator
