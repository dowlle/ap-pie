"""Serve restricted-worker schema output only for its exact release bytes."""
import json


def lookup(path, version):
    if not path.exists():
        return None
    raw=path.read_bytes()
    if len(raw)>5*1024*1024:
        raise ValueError('Schema cache budget exceeded')
    data=json.loads(raw)
    if not isinstance(data,dict) or data.get('schema')!=1 or not isinstance(data.get('records'),dict):
        raise ValueError('Invalid discovery schema cache')
    record=data['records'].get(version.discovery_id)
    if record is None:
        return None
    if not isinstance(record,dict) or set(record)!={'sha256','schema'} or record['sha256']!=version.sha256:
        raise ValueError('Schema cache checksum mismatch')
    schema=record['schema']
    if schema is not None and (not isinstance(schema,dict) or not isinstance(schema.get('game'),str)
                               or not isinstance(schema.get('options'),list)):
        raise ValueError('Invalid derived schema output')
    return record
