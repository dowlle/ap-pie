"""Advisory option-level checking of a YAML against an apworld's schema.

FEAT-31 gap 2, identified 2026-08-17: `validation.validate_yaml` checks that
a document is a mapping with a name, a game and a matching game section. It
never checks the options themselves, so `goal: oxidefinl` or a range far out
of bounds sails through and fails at generation time - in the host's lap,
after they have collected twenty files, long after the person who could fix
it has left the page.

The builder schemas cached by FEAT-38 make this cheap now, so the check runs
at submit time and reports back to the submitter.

**Warn, never reject.** Three reasons this is advisory:

- a player may legitimately run a fork whose options differ from the indexed
  build, and refusing their file would be wrong
- `triggers` and weighted values are resolved by the generator, not by us; a
  value that looks invalid here can be perfectly valid there
- a schema we failed to derive must never become a reason to refuse a
  submission that would have generated fine

So a finding is information for the submitter, not a gate.
"""

from __future__ import annotations

from typing import Any

# Values Archipelago resolves at generation time rather than storing
# literally (Options.py:25-56). Any of these is valid for any option type
# and must never be reported.
_RANDOM_PREFIX = "random"

# Archipelago's own per-slot options, valid for every game and absent from a
# world's declared schema (see frontend lib/coreOptions).
_CORE_OPTIONS = {"progression_balancing", "accessibility"}

# Root keys AP itself understands, so their presence is not a stray option.
_ROOT_KEYS = {
    "name", "game", "description", "requires", "triggers", "linked_options",
}


def _is_random(value: Any) -> bool:
    return isinstance(value, str) and (
        value == _RANDOM_PREFIX or value.startswith(f"{_RANDOM_PREFIX}-")
    )


def check_options(game_section: dict, schema: dict | None) -> list[dict]:
    """Compare a YAML's game section against a derived builder schema.

    Returns a list of findings, each `{code, option, detail}`:

      unknown_option   the schema has no option by that name
      unknown_choice   a choice option given a value it does not offer
      out_of_range     a numeric option outside its declared range

    An empty list means nothing to report, which is also what an absent or
    underivable schema produces.
    """
    if not schema or not isinstance(game_section, dict):
        return []

    options = {o["name"]: o for o in schema.get("options", [])}
    if not options:
        return []

    findings: list[dict] = []
    for key, value in game_section.items():
        if key in _CORE_OPTIONS or key == "triggers":
            continue
        opt = options.get(key)
        if opt is None:
            findings.append({
                "code": "unknown_option",
                "option": key,
                "detail": f"'{key}' is not an option this version of the game declares.",
            })
            continue

        # A weighted value ({value: weight}) is resolved by the generator;
        # checking each branch is possible but the failure mode we are
        # chasing is typos in plain values, so leave dicts alone.
        if isinstance(value, dict) or _is_random(value):
            continue

        if opt.get("type") == "choice" and opt.get("choices"):
            valid = {str(c) for c in opt["choices"]}
            if str(value) not in valid:
                findings.append({
                    "code": "unknown_choice",
                    "option": key,
                    "detail": (
                        f"'{value}' is not one of the accepted values for {key} "
                        f"({', '.join(sorted(valid))})."
                    ),
                })
        elif opt.get("type") == "range":
            lo, hi = opt.get("min"), opt.get("max")
            named = opt.get("named_values") or {}
            if isinstance(value, str) and value in named:
                continue
            try:
                num = int(value)
            except (TypeError, ValueError):
                findings.append({
                    "code": "out_of_range",
                    "option": key,
                    "detail": f"{key} expects a number; got '{value}'.",
                })
                continue
            if lo is not None and hi is not None and not (lo <= num <= hi):
                findings.append({
                    "code": "out_of_range",
                    "option": key,
                    "detail": f"{key} accepts {lo} to {hi}; got {num}.",
                })

    # Cap the report: a YAML written for a completely different game would
    # otherwise produce one finding per option and drown the useful ones.
    return findings[:20]


def check_document(doc: dict, game_name: str, schema: dict | None) -> list[dict]:
    """Check a whole parsed YAML document. Ignores root keys AP owns."""
    if not isinstance(doc, dict):
        return []
    section = doc.get(game_name)
    findings = check_options(section if isinstance(section, dict) else {}, schema)
    for key in doc:
        if key in _ROOT_KEYS or key == game_name:
            continue
        # A stray root key is usually an option written one level too high,
        # which the generator rejects outright with a confusing message.
        findings.append({
            "code": "unknown_option",
            "option": key,
            "detail": (
                f"'{key}' sits at the top level. Game options belong inside "
                f"the '{game_name}' section."
            ),
        })
    return findings[:20]
