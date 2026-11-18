"""Attach public provenance without inferring a report from version alone."""
import re
import json
import logging
import math
from pathlib import Path
from functools import lru_cache
from datetime import date

_RESULT_FIELDS = ("verdict", "default_rate", "worst_hook", "worst_hook_rate", "seeds", "fuzzed_at")


@lru_cache(maxsize=4)
def load_provenance(seed, overlay, stamp):
    records = []
    fields = {"module", "version", "sha256", "report_url", *_RESULT_FIELDS}
    for path in (seed, overlay):
        source = Path(path)
        if not source.is_file():
            continue
        try:
            if source.stat().st_size > 5 * 1024 * 1024:
                raise ValueError("Evidence file exceeds budget")
            payload = json.loads(source.read_text())
            if set(payload) != {"schema", "records"} or payload["schema"] != 1 or not isinstance(payload["records"], list) or len(payload["records"]) > 10000:
                raise ValueError("Invalid provenance schema")
            checked = []
            for record in payload["records"]:
                if not isinstance(record, dict) or set(record) != fields:
                    raise ValueError("Invalid provenance record")
                if not all(isinstance(record[field], str) for field in ("module", "version", "sha256", "report_url", "verdict", "worst_hook", "fuzzed_at")):
                    raise ValueError("Invalid provenance strings")
                if not re.fullmatch(r"[0-9a-f]{64}", record["sha256"]) or not github_report_url(record["report_url"]) or "/actions/runs/" not in record["report_url"]:
                    raise ValueError("Invalid run identity")
                if not re.fullmatch(r"[A-Za-z0-9_.-]{1,160}", record["module"]) or not 0 < len(record["version"]) <= 160:
                    raise ValueError("Invalid release identity")
                if date.fromisoformat(record["fuzzed_at"]).isoformat() != record["fuzzed_at"]:
                    raise ValueError("Invalid result date")
                if record["verdict"] not in {"clean", "flaky", "broken"} or type(record["seeds"]) is not int or record["seeds"] <= 0:
                    raise ValueError("Invalid test outcome")
                if not all(type(record[field]) in (int, float) and math.isfinite(record[field]) and 0 <= record[field] <= 1 for field in ("default_rate", "worst_hook_rate")):
                    raise ValueError("Invalid test rate")
                checked.append(record)
            records.extend(checked)
        except (ValueError, OSError, TypeError):
            logging.getLogger(__name__).warning("Invalid fuzz provenance; retaining recorded results without inferred links")
    return records

_REPORT = "https://github.com/dowlle/Archipelago-index/pull/754"
_HISTORICAL = {
    "borderlands2": ["0.5.2"], "dc1": ["0.4.4.1", "0.5.2", "0.5.5", "0.5.8"],
    "ffvcd": ["83.1"], "ladx_beta": ["13.4.2"], "mariomissing": ["0.0.2"],
    "mk64": ["mk64/0.2.5"], "mm_recomp": ["0.9.5a"], "mmbn6": ["0.1.1"],
    "papermario": ["0.6.3", "0.6.4"], "pharcryption": ["1.1.0"], "ufouria": ["0.0.1.post4"],
}
_EXPECTED = {
    (name, version): (5000, 1.0, 1.0)
    for name, versions in _HISTORICAL.items() for version in versions
}
_EXPECTED.update({("crash2", "0.4.0"): (5000, .9996, .9996), ("crash2", "0.4.1"): (2134, 1.0, 1.0)})

def github_report_url(value):
    if not isinstance(value, str):
        return None
    return value if re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/(?:pull|issues|actions/runs)/[0-9]+(?:[/?#][A-Za-z0-9_./?#=&%-]*)?", value) else None

def attach_fuzz_evidence(world, head, provenance=()):
    for version in world.versions:
        result = version.fuzz_result
        if result is None and getattr(version, 'discovered', False):
            exact = [r for r in provenance if r['module'] == world.name and
                     r['version'] == version.version and r['sha256'] == version.sha256]
            if exact:
                from ap_lib.apworld_index import FuzzResult
                # Keep the strongest recorded warning when multiple runs exist.
                chosen = max(exact, key=lambda r: ({'clean': 0, 'flaky': 1, 'broken': 2}[r['verdict']], r['fuzzed_at']))
                result = FuzzResult(**{field: chosen[field] for field in _RESULT_FIELDS}, report_url=chosen['report_url'])
                version.fuzz_result = result
        if result is None:
            continue
        result.report_url = github_report_url(result.report_url)
        matched = next((r for r in provenance if r["module"] == world.name and r["version"] == version.version
                        and r["sha256"] == version.sha256 and all(r[field] == getattr(result, field) for field in _RESULT_FIELDS)), None)
        if matched:
            result.report_url = github_report_url(matched["report_url"])
        expected = _EXPECTED.get((world.name, version.version))
        if not result.report_url and expected and result.verdict == "broken" and result.fuzzed_at == "2026-08-29" and result.worst_hook == "default" and (result.seeds, result.default_rate, result.worst_hook_rate) == expected:
            result.report_url = _REPORT
        if head and re.fullmatch(r"[0-9a-f]{40}", head) and re.fullmatch(r"[A-Za-z0-9_.-]+", world.name):
            result.record_url = f"https://github.com/dowlle/Archipelago-index/blob/{head}/index/{world.name}.toml"
