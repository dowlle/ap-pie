"""Validate and merge verified discovery releases without executing archives."""
import copy
import hashlib
import json
import re
import math
from pathlib import Path
from urllib.parse import urlsplit
from ap_lib.apworld_index import APWorldInfo, APWorldVersion, _version_sort_key


def load(path):
    if not path.exists():
        return {'schema': 1, 'releases': [], 'queue': {}}
    if path.stat().st_size > 5 * 1024 * 1024:
        raise ValueError('Discovery metadata too large')
    raw = path.read_bytes()
    if len(raw) > 5 * 1024 * 1024:
        raise ValueError('Discovery metadata too large')
    data = json.loads(raw)
    if not isinstance(data,dict) or data.get('schema') != 1 or not isinstance(data.get('releases'), list):
        raise ValueError('Invalid discovery schema')
    if len(data['releases']) > 10000:
        raise ValueError('Too many discovery releases')
    seen = set()
    for r in data['releases']:
        if not isinstance(r, dict) or not isinstance(r.get('sha256'),str) or not re.fullmatch('[a-f0-9]{64}', r['sha256']):
            raise ValueError('Invalid release checksum')
        module, version = r.get('module'), r.get('version')
        if not isinstance(module,str) or not re.fullmatch('[A-Za-z0-9_ .-]{1,160}',module) or module in ('.','..'):
            raise ValueError('Invalid release module')
        if not isinstance(version,str) or not 0 < len(version) <= 200 or any(ord(c)<32 for c in version):
            raise ValueError('Invalid release version')
        expected = hashlib.sha256(json.dumps((module,version,r['sha256']),separators=(',',':')).encode()).hexdigest()
        if r.get('id') != expected or expected in seen:
            raise ValueError('Invalid or duplicate release identity')
        seen.add(expected)
        if not isinstance(r.get('url'),str) or len(r['url'])>4000:
            raise ValueError('Invalid release URL')
        u=urlsplit(r['url'])
        if u.scheme!='https' or u.hostname!='github.com' or u.username or u.password or u.port not in (None,443) or u.query or u.fragment:
            raise ValueError('Invalid release source')
        if not re.fullmatch(r'/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/releases/download/[^/]+/[^/]+\.apworld',u.path):
            raise ValueError('Release URL is not an APWorld artifact')
        if not isinstance(r.get('source'),dict) or not isinstance(r.get('held'),bool):
            raise ValueError('Invalid release metadata')
        timestamp=r.get('verified_at')
        if isinstance(timestamp,bool) or not isinstance(timestamp,(int,float)) or not math.isfinite(timestamp) or timestamp<0:
            raise ValueError('Invalid verification timestamp')
        source=r['source']
        for key in ('name','home','stability','setup_guide','tracker'):
            value=source.get(key)
            if value is not None and (not isinstance(value,str) or len(value)>4000):
                raise ValueError('Invalid source metadata')
        for key in ('home','setup_guide','tracker'):
            value=source.get(key)
            if value and urlsplit(value).scheme not in ('http','https'):
                raise ValueError('Unsafe source link')
        for key in ('supported','disabled'):
            if key in source and not isinstance(source[key],bool):
                raise ValueError('Invalid source flag')
        jobs=r.get('jobs',{})
        if not isinstance(jobs,dict) or any(k not in ('security','generation','guide') or v not in ('queued','running','retry','blocked','completed') for k,v in jobs.items()):
            raise ValueError('Invalid discovery jobs')
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
