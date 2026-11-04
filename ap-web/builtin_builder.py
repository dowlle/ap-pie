"""Serve frozen official template schemas without importing world code."""
import json
from functools import lru_cache
from pathlib import Path

@lru_cache(maxsize=1)
def _records():
    path = Path(__file__).with_name('builtin_schemas') / 'catalog.json'
    try:
        return json.loads(path.read_text(encoding='utf-8'))['worlds']
    except (OSError, ValueError, KeyError):
        return {}

def builtin_record(world, version=None):
    if not getattr(world, 'is_builtin', False) or world.disabled:
        return None
    record = _records().get(world.name)
    if not record or record['game'] != world.game_name:
        return None
    if version is not None and version != record['version']:
        return None
    return record

def build_versions(world):
    """Buildable versions in index order: the default first."""
    from ap_lib.apworld_index import is_test_build

    versions = [
        {'version': v.version, 'test_build': is_test_build(v.version)}
        for v in world.versions if v.url or v.local
    ]
    record = builtin_record(world)
    if record:
        versions.append({'version': record['version'], 'test_build': False})
    return versions
