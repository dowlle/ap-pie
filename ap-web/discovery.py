"""Validate and merge verified discovery releases without executing archives."""
import copy
import hashlib
import json
import re
import math
import logging
import threading
from pathlib import Path
from urllib.parse import urlsplit
from ap_lib.apworld_index import APWorldInfo, APWorldVersion, _version_sort_key

_valid_snapshots = {}
_snapshot_lock = threading.Lock()
_logger = logging.getLogger(__name__)


def load_for_serving(path):
    """Keep the last validated snapshot if a later replacement is malformed.

    A missing file is an intentional overlay rollback. Invalid contents are
    rejected as a whole, without logging their potentially private values.
    """
    key = str(path.resolve())
    with _snapshot_lock:
        try:
            data = load(path)
        except (ValueError, OSError, TypeError, KeyError, OverflowError):
            _logger.warning('Rejected invalid discovery snapshot')
            return copy.deepcopy(_valid_snapshots.get(key, {'schema': 1, 'releases': [], 'queue': {}}))
        _valid_snapshots[key] = data
        return copy.deepcopy(data)


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
    policies=data.get('policies',[])
    if not isinstance(policies,list) or len(policies)>5000:
        raise ValueError('Invalid policy count')
    for policy in policies:
        if not isinstance(policy,dict) or set(policy)!={'module','version'}:
            raise ValueError('Invalid public policy fields')
        if not isinstance(policy['module'],str) or not re.fullmatch(r'[A-Za-z0-9_ .-]{1,160}',policy['module']) or policy['module'] in ('.','..'):
            raise ValueError('Invalid policy module')
        if not isinstance(policy['version'],str) or not 0<len(policy['version'])<=160 or any(ord(c)<32 for c in policy['version']):
            raise ValueError('Invalid policy version')
    queue=data.get('queue',{})
    if not isinstance(queue,dict) or set(queue)-{'sources','releases','holds','candidates','jobs'}:
        raise ValueError('Invalid public queue metadata')
    def count(value):
        return isinstance(value,int) and not isinstance(value,bool) and 0<=value<=10000000
    for key in ('sources','releases','holds'):
        if key in queue and not count(queue[key]):
            raise ValueError('Invalid queue count')
    for key in ('candidates','jobs'):
        states=queue.get(key,{})
        allowed={'queued','running','retry','blocked','verified'} if key=='candidates' else {'queued','running','retry','blocked','completed'}
        if not isinstance(states,dict) or any(k not in allowed or not count(v) for k,v in states.items()):
            raise ValueError('Invalid queue states')
    seen = set()
    for r in data['releases']:
        if not isinstance(r,dict) or set(r)-{'id','module','version','sha256','url','verified_at','source','held','jobs'}:
            raise ValueError('Unknown release metadata fields')
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
        if set(source)-{'name','home','stability','setup_guide','tracker','supported','disabled'}:
            raise ValueError('Unknown source metadata fields')
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
        if not isinstance(jobs,dict) or any(k not in ('security','generation','guide','schema') or v not in ('queued','running','retry','blocked','completed') for k,v in jobs.items()):
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
            old.discovery_id=r['id']
            old.discovery_held=r['held']
            old.discovery_jobs=dict(r.get('jobs', {}))
            continue
        # Full immutable history stays in the snapshot; the version resolver
        # selects the most recently verified bytes for each version label.
        w.versions=[v for v in w.versions if v.version!=r['version']]
        v=APWorldVersion(version=r['version'],url=r['url'],sha256=r['sha256'])
        v.discovered=True
        v.discovery_id=r['id']
        v.discovery_held=r['held']
        v.discovery_jobs=dict(r.get('jobs', {}))
        w.versions.append(v)
        w.versions.sort(key=lambda v:_version_sort_key(v.version),reverse=True)
    policies={(p['module'],p['version']) for p in data.get('policies',[])}
    for world in worlds:
        for version in world.versions:
            version.policy_held=(world.name,version.version) in policies or (world.name,'*') in policies
            if getattr(version,'discovery_id',None) and version.policy_held:
                version.discovery_held=True
    return worlds


def attach_public_metadata(world, data):
    """Policy holds are independent from checksum-matched security verdicts."""
    versions = {v.version: v for v in world.versions}
    for row in data['versions']:
        version = versions[row['version']]
        row['policy_hold'] = {'summary': 'This release has an unresolved policy or security hold. Discovery does not clear that hold.'} if getattr(version,'policy_held',False) else None
        if getattr(version, 'discovery_id', None):
            row['discovery'] = {
                'id': version.discovery_id,
                'record_url': '/api/apworlds/intake/releases/' + version.discovery_id,
                'held': version.discovery_held,
                'jobs': dict(version.discovery_jobs),
                'policy_summary': ('This release has an unresolved policy or security hold. '
                                   'Discovery does not clear that hold.') if version.discovery_held else None,
            }
    return data
