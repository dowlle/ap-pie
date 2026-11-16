"""Serve restricted-worker schema output only for its exact release bytes."""
import json
from apworld_options_parser import BUILDER_SCHEMA_FORMAT_VERSION


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
    if (not isinstance(record,dict) or set(record)-{'sha256','schema','parser_version'}
            or not {'sha256','schema'} <= set(record) or record['sha256']!=version.sha256):
        raise ValueError('Schema cache checksum mismatch')
    schema=record['schema']
    if schema is not None and (not isinstance(schema,dict) or not isinstance(schema.get('game'),str)
                               or not isinstance(schema.get('options'),list)):
        raise ValueError('Invalid derived schema output')
    # The exact bytes can stay unchanged while parser semantics improve.
    # Old positive and negative results must be re-derived by the worker,
    # never by downloading or executing a package inside a web request.
    if schema is not None:
        if schema.get('_format_version') != BUILDER_SCHEMA_FORMAT_VERSION:
            return None
    elif record.get('parser_version') != BUILDER_SCHEMA_FORMAT_VERSION:
        return None
    return record
