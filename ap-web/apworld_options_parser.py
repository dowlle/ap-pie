"""Parse option definitions from .apworld files to generate template data."""

from __future__ import annotations

import ast
import io
import re
import zipfile
from pathlib import Path


BUILDER_SCHEMA_FORMAT_VERSION = 2


def parse_apworld_options(apworld_path: Path) -> dict | None:
    """Parse an .apworld zip on disk and extract game options.

    Thin wrapper over `parse_apworld_options_bytes` for callers that have a
    file path (the legacy /api/templates local-worlds scan).
    """
    try:
        data = Path(apworld_path).read_bytes()
    except OSError:
        return None
    return parse_apworld_options_bytes(data, stem_hint=Path(apworld_path).stem)


def parse_apworld_options_bytes(data: bytes, stem_hint: str | None = None) -> dict | None:
    """Parse .apworld zip bytes and extract game options as template data.

    FEAT-38: byte-level entry point so Tier-1 builder schemas can be derived
    from apworlds fetched over the wire (a room's pinned version) without
    touching disk. Returns a dict matching template_parser.parse_template()
    ({game, ap_version, world_version, categories, options}), or None if the
    apworld cannot be parsed.

    `stem_hint` is the expected inner module directory name (usually the
    index key / filename stem). When it doesn't match the zip layout the
    module directory is auto-detected from the archive instead, so index
    keys that differ from the packaged module name still parse.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError):
        return None

    # Hardening (branch audit 2026-07-22): pathological source (deep AST
    # nesting, huge literals) can raise RecursionError/MemoryError out of
    # ast.parse. Fail to None instead of killing the worker; callers
    # negative-cache the result.
    try:
        return _parse_zip(zf, stem_hint)
    except (RecursionError, MemoryError):
        return None


def _parse_zip(zf: zipfile.ZipFile, stem_hint: str | None) -> dict | None:
    stem = _detect_module_dir(zf, stem_hint)
    if not stem:
        return None

    # Find the game name (usually in __init__.py, sometimes in world.py)
    init_src = _read_member(zf, f"{stem}/__init__.py")
    game_name = _extract_game_name(zf, stem)
    if not game_name:
        return None

    # Find Options.py; some small worlds define options inline in __init__.py
    options_src = _find_options_source(zf, stem)
    if not options_src:
        options_src = init_src
    if not options_src:
        return None

    # Option groups may live in either file; scan both for the class->group map
    group_map = _parse_option_groups([s for s in (options_src, init_src) if s])

    literal_names = _collect_module_literals(zf, stem)
    options = _parse_options_source(options_src, group_map, literal_names)
    # An empty option list is a real answer, not a failure. A world can
    # legitimately declare no options of its own (or only ones we
    # deliberately do not render), and a YAML with name / game / requires
    # plus Archipelago's own options is valid and submittable. Returning
    # None here used to send those players away with "grab the template
    # from the setup guide" for a game the builder can handle fine.
    # None stays reserved for "this archive could not be understood",
    # which the callers above still return.

    categories = []
    for opt in options:
        if opt["category"] not in categories:
            categories.append(opt["category"])

    return {
        "_format_version": BUILDER_SCHEMA_FORMAT_VERSION,
        "game": game_name,
        "ap_version": "",
        "world_version": "",
        "categories": categories,
        "options": options,
    }


def _detect_module_dir(zf: zipfile.ZipFile, stem_hint: str | None) -> str | None:
    """Pick the inner module directory (the one holding __init__.py)."""
    names = set(zf.namelist())
    if stem_hint:
        for candidate in (stem_hint, stem_hint.lower()):
            if f"{candidate}/__init__.py" in names:
                return candidate
    # Fall back: any top-level directory with an __init__.py. Sorted so the
    # pick is deterministic when an archive carries more than one (rare).
    tops = sorted({n.split("/", 1)[0] for n in names if "/" in n})
    for top in tops:
        if f"{top}/__init__.py" in names:
            return top
    return None


# Hardening (branch audit 2026-07-22, low finding): a hostile zip can lie
# about member sizes and decompress far past its header claim. Bound the
# actual decompressed bytes read per source member; real Options.py files
# are tens of KB, so 5 MB is generous.
_MAX_MEMBER_BYTES = 5 * 1024 * 1024


def _read_member(zf: zipfile.ZipFile, name: str) -> str | None:
    if name not in zf.namelist():
        return None
    try:
        with zf.open(name) as fh:
            raw = fh.read(_MAX_MEMBER_BYTES + 1)
        if len(raw) > _MAX_MEMBER_BYTES:
            return None
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return None


def _extract_game_name(zf: zipfile.ZipFile, stem: str) -> str | None:
    """Extract the game name (the World class's `game` attribute).

    Usually declared in __init__.py, but some worlds keep the World class in
    a sibling module (e.g. Schedule_I's world.py), and some assign a
    module-level constant instead of a literal (stardew's `game: str =
    STARDEW_VALLEY`, autopelago's `game = GAME_NAME`). Scan the module's own
    (non-test) sources, __init__.py first, literals before constant
    resolution.
    """
    files = _module_py_files(zf, stem)
    init_name = f"{stem}/__init__.py"
    if init_name in files:
        files = [init_name] + [f for f in files if f != init_name]

    literal_re = re.compile(r'^\s+game\s*(?::\s*str\s*)?=\s*["\'](.+?)["\']', re.MULTILINE)
    ident_re = re.compile(r'^\s+game\s*(?::\s*str\s*)?=\s*([A-Za-z_]\w*)\s*$', re.MULTILINE)

    sources: dict[str, str] = {}
    ident = None
    for name in files:
        src = _read_member(zf, name)
        if not src:
            continue
        sources[name] = src
        m = literal_re.search(src)
        if m:
            return m.group(1)
        if ident is None:
            im = ident_re.search(src)
            if im:
                ident = im.group(1)

    if ident:
        const_re = re.compile(
            rf'^{re.escape(ident)}\s*(?::\s*[\w.\[\]]+\s*)?=\s*["\'](.+?)["\']',
            re.MULTILINE,
        )
        for name in files:
            src = sources.get(name)
            if not src:
                continue
            cm = const_re.search(src)
            if cm:
                return cm.group(1)
    return None


def _module_py_files(zf: zipfile.ZipFile, stem: str) -> list[str]:
    """The module's own .py files, test dirs excluded, shallow paths first."""
    prefix = stem.lower() + "/"
    out = [
        n for n in zf.namelist()
        if n.lower().startswith(prefix) and n.endswith(".py")
        and "/test" not in n.lower()
    ]
    out.sort(key=lambda n: (n.count("/"), n.lower()))
    return out


def _find_options_source(zf: zipfile.ZipFile, stem: str) -> str | None:
    """Find and read the Options.py file from the apworld."""
    # Common patterns: stem/Options.py, stem/options.py, stem/StemOptions.py,
    # options/options.py in a subpackage. Prefer an exact `options.py`
    # basename over suffix matches (stardew ships forced_options.py etc.),
    # then shallower paths.
    candidates = [
        n for n in _module_py_files(zf, stem)
        if n.lower().endswith("options.py")
    ]
    candidates.sort(
        key=lambda n: (
            0 if n.rsplit("/", 1)[-1].lower() == "options.py" else 1,
            n.count("/"),
        )
    )
    for name in candidates:
        src = _read_member(zf, name)
        if src:
            return src
    return None


# Map of AP option base classes to our template types. Values match what
# template_parser.parse_template() emits so both schema sources render
# through the same form controls.
_AP_TYPE_MAP = {
    "Choice": "choice",
    "TextChoice": "choice",
    "Range": "range",
    "NamedRange": "range",
    "Toggle": "toggle",
    "DefaultOnToggle": "toggle",
    "OptionSet": "list",
    "OptionList": "list",
    "ItemSet": "list",
    "LocationSet": "list",
    "OptionDict": "dict",
    "OptionCounter": "dict",
    "ItemDict": "dict",
    "FreeText": "text",
}

# Aggregate dataclasses and tombstones - never form fields.
_SKIP_BASES = {"PerGameCommonOptions", "CommonOptions", "Removed"}

# Archipelago-provided option classes a world can pull into its own options
# dataclass. They live in AP core, so their class body is not in the archive
# and the normal in-file base resolution finds nothing to render.
#
# Only options that are per-world by nature and that we can render belong
# here. `death_link` is the case that matters: it is a mixin a game opts into
# (`DeathLinkMixin`, Archipelago Options.py:1727), so finding it in a world's
# dataclass is precisely the signal that this game supports it.
#
# Deliberately absent: StartInventoryPool, LocalItems, ExcludeLocations and
# the rest of the item/location-name family. Those need exact item and
# location names, which cannot be derived without executing the world, so the
# builder points at the review step's YAML editor rather than offering a
# field that fails at generation time.
_AP_CORE_OPTIONS: dict[str, dict] = {
    "DeathLink": {
        "type": "toggle",
        "default": False,
        "display_name": "Death Link",
        "description": (
            "When you die, everyone who enabled death link dies. "
            "Of course, the reverse is true too."
        ),
    },
}


def _parse_option_groups(sources: list[str]) -> dict[str, str]:
    """Extract the apworld's own option_groups as a class-name -> group-name
    map. AP convention: a module-level list of OptionGroup("Name", [Cls, ...])
    calls (the variable is usually `<game>_option_groups` or `option_groups`).
    """
    groups: dict[str, str] = {}
    for src in sources:
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            value = getattr(node, "value", None)
            if not isinstance(node, (ast.Assign, ast.AnnAssign)) or not isinstance(value, ast.List):
                continue
            for el in value.elts:
                if not (isinstance(el, ast.Call) and _get_name(el.func) == "OptionGroup"):
                    continue
                if not el.args or not isinstance(el.args[0], ast.Constant):
                    continue
                group_name = el.args[0].value
                if not isinstance(group_name, str):
                    continue
                if len(el.args) >= 2 and isinstance(el.args[1], ast.List):
                    for member in el.args[1].elts:
                        cls_name = _get_name(member)
                        if cls_name:
                            groups[cls_name] = group_name
    return groups


def _parse_options_source(
    src: str,
    group_map: dict[str, str] | None = None,
    literal_names: dict[str, object] | None = None,
) -> list[dict]:
    """Parse option class definitions from Python source code using AST."""
    group_map = group_map or {}
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []

    class_defs: dict[str, ast.ClassDef] = {}
    order: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name not in class_defs:
            class_defs[node.name] = node
            order.append(node.name)

    # The PerGameCommonOptions dataclass is the source of truth for option
    # names: its annotated field names are the YAML keys AP actually reads,
    # and they routinely diverge from the class names (e.g. pokepelago's
    # `type_locks: EnableTypeLocks`, `route_locks_enabled: RouteLocks`).
    # Snake-casing the class name emits keys the generator silently ignores,
    # so when the dataclass is present it also decides membership + order.
    field_map: list[tuple[str, str]] = []  # (yaml_key, class_name), dataclass order
    for cls_name in order:
        node = class_defs[cls_name]
        if not any(_get_name(b) in ("PerGameCommonOptions", "CommonOptions") for b in node.bases):
            continue
        for item in node.body:
            if isinstance(item, ast.AnnAssign):
                key = _get_name(item.target)
                ann = _get_name(item.annotation)
                if key and ann:
                    field_map.append((key, ann))
        if field_map:
            break

    def resolve_ap_base(name: str, seen: set[str]) -> str | None:
        """Resolve which AP option base a class ultimately derives from,
        following in-file base classes so `class RouteLocks(BaseLockToggle)`
        picks up BaseLockToggle's kind. Returns the _AP_TYPE_MAP key (the AP
        class name) rather than the mapped template type, because some bases
        carry semantics beyond their type: DefaultOnToggle implies default
        True even when the option class body never assigns `default`."""
        node = class_defs.get(name)
        if node is None or name in seen:
            return None
        seen.add(name)
        for base in node.bases:
            base_name = _get_name(base)
            if base_name is None:
                continue
            if base_name in _SKIP_BASES:
                return None
            if base_name in _AP_TYPE_MAP:
                return base_name
            inherited = resolve_ap_base(base_name, seen)
            if inherited:
                return inherited
        return None

    def collect_fields(name: str, seen: set[str]) -> dict:
        """Collect class-body assignments, letting subclasses override the
        fields their in-file parents declared (defaults often live on a
        shared base)."""
        node = class_defs.get(name)
        if node is None or name in seen:
            return {}
        seen.add(name)
        fields: dict = {}
        for base in node.bases:
            base_name = _get_name(base)
            if base_name and base_name in class_defs:
                fields.update(collect_fields(base_name, seen))
        for item in node.body:
            targets: list[ast.AST] = []
            value = None
            if isinstance(item, ast.Assign):
                targets = item.targets
                value = item.value
            elif isinstance(item, ast.AnnAssign) and item.value is not None:
                targets = [item.target]
                value = item.value
            for target in targets:
                tname = _get_name(target)
                if tname:
                    fields[tname] = value
        return fields

    if field_map:
        candidates = [(key, cls) for key, cls in field_map if cls in class_defs]
        # Fields whose option class comes from AP core rather than this
        # apworld (see _AP_CORE_OPTIONS). Without this a world that declares
        # only core options - BKBK But It's Only Furnace Fun declares exactly
        # `start_inventory_from_pool` and `death_link` - yields no options at
        # all and looks unparseable.
        core_fields = [
            (key, cls) for key, cls in field_map
            if cls not in class_defs and cls in _AP_CORE_OPTIONS
        ]
    else:
        # No aggregate dataclass in this source (older worlds, or options
        # defined via the legacy dict) - fall back to every option-typed
        # class in file order, named by snake_cased class name.
        candidates = [(_camel_to_snake(c), c) for c in order]
        core_fields = []

    options = []
    for opt_name, cls_name in core_fields:
        spec = _AP_CORE_OPTIONS[cls_name]
        options.append({
            "name": opt_name,
            "display_name": spec["display_name"],
            "description": spec["description"],
            "category": group_map.get(cls_name, "Game Options"),
            "type": spec["type"],
            "default": spec["default"],
        })
    for opt_name, cls_name in candidates:
        node = class_defs[cls_name]
        if cls_name.startswith("_"):
            continue
        if any(_get_name(b) in _SKIP_BASES for b in node.bases):
            continue
        ap_base = resolve_ap_base(cls_name, set())
        opt_type = _AP_TYPE_MAP.get(ap_base) if ap_base else None
        if opt_type is None:
            continue

        raw = collect_fields(cls_name, set())

        # `Visibility.none` marks hidden/deprecated options (e.g. superseded
        # legacy toggles). Emitting them would fight the option that replaced
        # them, so they never reach the form.
        vis = raw.get("visibility")
        if vis is not None:
            if isinstance(vis, ast.Attribute) and vis.attr == "none":
                continue
            if isinstance(vis, ast.Constant) and vis.value == 0:
                continue

        display_name = _get_literal(raw.get("display_name"), literal_names)
        description = (ast.get_docstring(node) or "").strip()
        default = _get_literal(raw.get("default"), literal_names)
        range_start = _get_literal(raw.get("range_start"), literal_names)
        range_end = _get_literal(raw.get("range_end"), literal_names)
        valid_keys = _get_literal(raw.get("valid_keys"), literal_names)
        special_range_names = _get_literal(raw.get("special_range_names"), literal_names)
        option_values = {}
        for fname, fvalue in raw.items():
            if fname.startswith("option_"):
                option_values[fname[7:]] = _get_literal(fvalue, literal_names)

        category = group_map.get(cls_name, "Game Options")
        base = {
            "name": opt_name,
            "description": description,
            "category": category,
        }
        if isinstance(display_name, str) and display_name:
            base["display_name"] = display_name

        if opt_type == "choice" and option_values:
            # Sort choices by their numeric value
            sorted_choices = sorted(option_values.items(), key=lambda x: x[1] if isinstance(x[1], int) else 0)
            choices = [k for k, v in sorted_choices]
            default_val = choices[0]
            if isinstance(default, int):
                for k, v in sorted_choices:
                    if v == default:
                        default_val = k
                        break
            elif isinstance(default, str) and default in option_values:
                default_val = default
            options.append({
                **base,
                "type": "choice",
                "default": default_val,
                "choices": choices,
            })

        elif opt_type == "range" and range_start is not None and range_end is not None:
            named_values = None
            if isinstance(special_range_names, dict) and special_range_names:
                named_values = {
                    str(k): v for k, v in special_range_names.items()
                    if isinstance(v, int)
                }
            options.append({
                **base,
                "type": "range",
                "default": default if isinstance(default, int) else range_start,
                "min": range_start,
                "max": range_end,
                "named_values": named_values or None,
            })

        elif opt_type == "toggle":
            # DefaultOnToggle's default=1 lives on the AP library class, not
            # in the apworld source, so a class body without an explicit
            # `default` must inherit True from the base (bit CTR: 8 options
            # rendered default-off in the builder, 2026-07-22).
            inherited_on = ap_base == "DefaultOnToggle"
            default_bool = bool(default) if default is not None else inherited_on
            options.append({
                **base,
                "type": "toggle",
                "default": default_bool,
            })

        elif opt_type == "list":
            default_list = sorted(default) if isinstance(default, (set, frozenset)) else (
                list(default) if isinstance(default, (list, tuple)) else []
            )
            entry = {
                **base,
                "type": "list",
                "default": default_list,
            }
            if isinstance(valid_keys, (set, frozenset)):
                entry["choices"] = sorted(valid_keys)
            elif isinstance(valid_keys, (list, tuple)):
                entry["choices"] = list(valid_keys)
            if "choices" not in entry and not default_list:
                # Free-form list with no key hints renders as nothing useful;
                # still emit so curated overlays (Tier 2) can supply the keys.
                entry["choices"] = None
            options.append(entry)

        elif opt_type == "dict":
            default_dict = dict(default) if isinstance(default, dict) else {}
            entry = {
                **base,
                "type": "dict",
                "default": default_dict,
            }
            if isinstance(valid_keys, (set, frozenset)):
                entry["valid_keys"] = sorted(valid_keys)
            elif isinstance(valid_keys, (list, tuple)):
                entry["valid_keys"] = list(valid_keys)
            options.append(entry)

        elif opt_type == "text":
            options.append({
                **base,
                "type": "text",
                "default": default if isinstance(default, str) else "",
            })

    return options


def _get_name(node: ast.AST | None) -> str | None:
    """Get a simple name from an AST node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


_LITERAL_CONSTRUCTORS = {
    "frozenset": frozenset,
    "set": set,
    "tuple": tuple,
    "list": list,
    "dict": dict,
    "sorted": sorted,
}


def _get_literal(
    node: ast.AST | None,
    literal_names: dict[str, object] | None = None,
):
    """Safely evaluate a constant/literal AST node.

    Also evaluates single-argument calls to the builtin container
    constructors (`frozenset({...})`, `set([...])`, ...), which
    ast.literal_eval rejects — apworlds routinely write OptionSet defaults
    as `default = frozenset({...})` (bit CTR's warp_pad_shuffle_categories,
    2026-07-22)."""
    if node is None:
        return None
    if isinstance(node, ast.Name) and literal_names is not None:
        return literal_names.get(node.id)
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        pass
    if isinstance(node, ast.Call) and not node.keywords and len(node.args) <= 1:
        fn = _get_name(node.func)
        ctor = _LITERAL_CONSTRUCTORS.get(fn or "")
        if ctor is not None:
            if not node.args:
                return ctor()
            inner = _get_literal(node.args[0], literal_names)
            if inner is not None:
                try:
                    return ctor(inner)
                except (ValueError, TypeError):
                    return None
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in {"keys", "values"}
            and not node.args
        ):
            owner = _get_literal(node.func.value, literal_names)
            if isinstance(owner, dict):
                return owner.keys() if node.func.attr == "keys" else owner.values()
    return None


def _collect_module_literals(zf: zipfile.ZipFile, stem: str) -> dict[str, object]:
    """Resolve safe module constants used by option metadata.

    APWorlds commonly import a literal collection into Options.py and wrap
    it in ``frozenset(...)`` for ``valid_keys``. Pokepelago is one example:
    ``GAME_REGIONS = list(REGION_DATA.keys())`` lives in data.py. No module
    code is executed here; only AST literals, safe container constructors,
    and ``dict.keys()/values()`` are evaluated.
    """
    assignments: list[tuple[str, ast.AST]] = []
    for member in _module_py_files(zf, stem):
        source = _read_member(zf, member)
        if not source:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                name = _get_name(node.targets[0])
                if name:
                    assignments.append((name, node.value))
            elif isinstance(node, ast.AnnAssign):
                name = _get_name(node.target)
                if name and node.value is not None:
                    assignments.append((name, node.value))

    resolved: dict[str, object] = {}
    pending = assignments
    for _ in range(8):
        next_pending: list[tuple[str, ast.AST]] = []
        progressed = False
        for name, value_node in pending:
            value = _get_literal(value_node, resolved)
            if value is None:
                next_pending.append((name, value_node))
                continue
            resolved[name] = value
            progressed = True
        pending = next_pending
        if not progressed:
            break
    return resolved


def _camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case."""
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    return s.lower()
