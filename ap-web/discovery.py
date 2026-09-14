"""Validate and merge verified discovery releases without executing archives."""
import copy
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from ap_lib.apworld_index import APWorldInfo, APWorldVersion, _version_sort_key


def load(path):
    if not path.exists():
        return {'schema': 1, 'releases': [], 'queue': {}}
    if path.stat().st_size > 5 * 1024 * 1024:
        raise ValueError('Discovery metadata too large')
    data = json.loads(path.read_text())
    if data.get('schema') != 1 or not isinstance(data.get('releases'), list):
        raise ValueError('Invalid discovery schema')
    seen = set()
    for r in data['releases']:
        if not isinstance(r, dict) or not re.fullmatch('[a-f0-9]{64}', r.get('sha256', '')):
            raise ValueError('Invalid release checksum')
        module, version = r.get('module'), r.get('version')
        if not isinstance(module,str) or not re.fullmatch('[A-Za-z0-9_ .-]{1,160}',module) or module in ('.','..'):
            raise ValueError('Invalid release module')
        if not isinstance(version,str) or not 0 < len(version) <= 200:
            raise ValueError('Invalid release version')
        expected = hashlib.sha256(json.dumps((module,version,r['sha256']),separators=(',',':')).encode()).hexdigest()
        if r.get('id') != expected or expected in seen:
            raise ValueError('Invalid or duplicate release identity')
        seen.add(expected)
        u=urlsplit(r.get('url',''))
        if u.scheme!='https' or u.hostname!='github.com' or u.username or u.password or u.port not in (None,443):
            raise ValueError('Invalid release source')
        if not isinstance(r.get('source'),dict) or not isinstance(r.get('held'),bool):
            raise ValueError('Invalid release metadata')
    return data


def merge(worlds, data):
    worlds=copy.deepcopy(worlds)
    lookup={w.name:w for w in worlds}
    for r in sorted(data['releases'],key=lambda r:r['verified_at']):
        w=lookup.get(r['module'])
        if w is None:
            source=r['source']
            w=APWorldInfo(name=r['module'],display_name=source.get('name') or r['module'],
                          game_name=source.get('name') or r['module'],home=source.get('home',''),
                          stability=source.get('stability'),setup_guide=source.get('setup_guide'))
            worlds.append(w)
            lookup[w.name]=w
        old=next((v for v in w.versions if v.version==r['version']),None)
        if old and old.sha256==r['sha256']:
            continue
        # Full immutable history stays in the snapshot; the version resolver
        # selects the most recently verified bytes for each version label.
        w.versions=[v for v in w.versions if v.version!=r['version']]
        v=APWorldVersion(version=r['version'],url=r['url'],sha256=r['sha256'])
        v.discovered=True
        v.discovery_id=r['id']
        v.discovery_held=r['held']
        w.versions.append(v)
        w.versions.sort(key=lambda v:_version_sort_key(v.version),reverse=True)
    return worlds
