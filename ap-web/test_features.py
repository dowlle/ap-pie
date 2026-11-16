"""Generation requires an explicit opt-in, including in fresh deployments."""

import os
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch

from flask import Flask

import config
from api.features import bp
from api.upload import bp as upload_bp


class GenerationFeatureTests(unittest.TestCase):
    def load_features(self, value=None):
        # Evaluate a fresh config without reloading the shared config module.
        with patch.dict(os.environ):
            os.environ.pop("FEATURE_GENERATION", None)
            if value is not None:
                os.environ["FEATURE_GENERATION"] = value
            namespace = runpy.run_path(str(Path(config.__file__)))
            return namespace["FEATURES"]

    def test_missing_generation_flag_defaults_off(self):
        self.assertFalse(self.load_features()["generation"])

    def test_empty_false_and_invalid_values_keep_generation_off(self):
        for value in ("", "false", "0", "no", "off", "invalid"):
            with self.subTest(value=value):
                self.assertFalse(self.load_features(value)["generation"])

    def test_explicit_opt_in_enables_generation(self):
        for value in ("true", "TRUE", "1", "yes", "on"):
            with self.subTest(value=value):
                self.assertTrue(self.load_features(value)["generation"])

    def test_feature_api_and_route_gate_follow_configuration(self):
        app = Flask(__name__)
        app.register_blueprint(bp)
        app.register_blueprint(upload_bp)
        client = app.test_client()
        for value, enabled in ((None, False), ("", False), ("true", True)):
            with self.subTest(value=value), patch.dict(config.FEATURES, self.load_features(value)):
                self.assertEqual(client.get("/api/features").get_json()["generation"], enabled)
                # An enabled upload reaches input validation without writing a file.
                response = client.post("/api/upload")
                self.assertEqual(response.status_code, 400 if enabled else 403)
                self.assertEqual(response.get_json(), {"error": "No file provided"} if enabled else {
                    "error": "The 'generation' feature is currently disabled on this server.",
                    "feature": "generation",
                    "enabled": False,
                })


if __name__ == "__main__":
    unittest.main()
