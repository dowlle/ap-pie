"""OPS-07: deployment metadata endpoint.

Tells the frontend which environment it is running in. Empty label = prod /
unlabelled, no visible banner. Non-empty label (e.g. "beta") triggers the
DeploymentBanner above the NavBar and PublicLayout header.

Public endpoint: the label is not a secret (it is announced to every page
visitor by the banner itself; the API just exposes the canonical source).
"""

from __future__ import annotations

from flask import Blueprint, jsonify

import config

bp = Blueprint("deployment", __name__)


@bp.route("/api/deployment")
def get_deployment():
    return jsonify({"label": config.DEPLOYMENT_LABEL})
