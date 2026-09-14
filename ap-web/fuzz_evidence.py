"""Attach public provenance without inferring a report from version alone."""
import re

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

def attach_fuzz_evidence(world, head):
    for version in world.versions:
        result = version.fuzz_result
        if result is None:
            continue
        result.report_url = github_report_url(result.report_url)
        expected = _EXPECTED.get((world.name, version.version))
        if not result.report_url and expected and result.verdict == "broken" and result.fuzzed_at == "2026-08-29" and result.worst_hook == "default" and (result.seeds, result.default_rate, result.worst_hook_rate) == expected:
            result.report_url = _REPORT
        if head and re.fullmatch(r"[0-9a-f]{40}", head) and re.fullmatch(r"[A-Za-z0-9_.-]+", world.name):
            result.record_url = f"https://github.com/dowlle/Archipelago-index/blob/{head}/index/{world.name}.toml"
