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
    versions = [{'version': v.version} for v in world.versions if v.url or v.local]
    record = builtin_record(world)
    if record:
        versions.append({'version': record['version']})
    return versions
