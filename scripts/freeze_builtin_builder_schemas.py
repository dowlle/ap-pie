#!/usr/bin/env python3
"""Freeze official built-in templates into JSON; never execute world modules."""
import argparse
import concurrent.futures
import hashlib
import json
import re
import sys
import io
import zipfile
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ap-web'))
import yaml
from template_parser import parse_template
from apworld_options_parser import parse_apworld_options_bytes

COMMON = {'progression_balancing', 'accessibility', 'local_items', 'non_local_items',
          'start_inventory', 'start_inventory_from_pool', 'start_hints',
          'start_location_hints', 'exclude_locations', 'priority_locations',
          'item_links', 'plando_items', 'plando_texts', 'plando_connections'}

def freeze(world, directory, source, reuse=False):
    url = 'https://archipelago.gg/static/generated/configs/' + quote(world['game_name'], safe='') + '.yaml'
    try:
        path = directory / (world['name'] + '.yaml')
        if reuse and path.exists():
            data = path.read_bytes()
        else:
            with urlopen(url, timeout=20) as response:
                data = response.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024:
            raise ValueError('template exceeds limit')
        path.write_bytes(data)
        document = yaml.safe_load(data.decode('utf-8-sig'))
        if document['game'] != world['game_name']:
            raise ValueError('game identity mismatch')
        schema = parse_template(path)
        # Static source types distinguish numeric OptionDicts from weights.
        module = source / 'worlds' / world['name']
        package = io.BytesIO()
        with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED) as archive:
            for member in sorted(module.rglob('*.py')):
                archive.write(member, str(member.relative_to(module.parent)))
        source_schema = parse_apworld_options_bytes(package.getvalue(), world['name'])
        source_options = {o['name']: o for o in (source_schema or {}).get('options', [])}
        for index, option in enumerate(schema['options']):
            source_option = source_options.get(option['name'])
            if source_option and source_option['type'] == 'dict':
                schema['options'][index] = {**source_option, 'default': document[document['game']][option['name']]}
        schema['options'] = [o for o in schema['options'] if o['name'] not in COMMON]
        missing = set(document[document['game']]) - COMMON - {o['name'] for o in schema['options']}
        for name in sorted(missing):
            default = document[document['game']][name]
            # Multiline OptionDict values are not weighted choice maps.
            # Never guess numeric-only maps: they could represent weights.
            if not isinstance(default, dict) or all(isinstance(v, int) for v in default.values()):
                raise ValueError('unparsed game option: ' + name)
            block = re.search(r'^  ' + re.escape(name) + r':\n((?:[ \t].*\n|\n)*)', data.decode('utf-8-sig'), re.M)
            description = '\n'.join(line.strip()[1:].strip() for line in block[1].splitlines() if line.strip().startswith('#')) if block else ''
            schema['options'].append({'name': name, 'type': 'dict', 'category': 'Game Options', 'description': description, 'default': default})
        schema['categories'] = list(dict.fromkeys(o['category'] for o in schema['options']))
        schema['_format_version'] = 6
        schema['world_version'] = ''  # bundled worlds are versioned by the AP release
        for option in schema['options']:
            if option['type'] == 'dict':
                option['dict_kind'] = 'mapping'
        version = schema['ap_version']
        if not version:
            raise ValueError('missing Archipelago release version')
        source_version = re.search(r'^__version__ = "([^"]+)"', (source / 'Utils.py').read_text(), re.M)
        if not source_version or source_version[1] != version:
            raise ValueError('template and source release versions differ')
        return world['name'], {'version': version, 'game': document['game'],
                               'source_url': url, 'template_sha256': hashlib.sha256(data).hexdigest(),
                               'schema': schema}, None
    except Exception as error:
        return world['name'], None, str(error)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--catalog', required=True, type=Path)
    ap.add_argument('--templates', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--source', required=True, type=Path, help='Clean matching official release source tree')
    ap.add_argument('--reuse-templates', action='store_true')
    args = ap.parse_args()
    args.templates.mkdir(parents=True, exist_ok=True)
    worlds = [w for w in json.loads(args.catalog.read_text()) if w['is_builtin'] and not w['disabled']]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda w: freeze(w, args.templates, args.source, args.reuse_templates), worlds))
    records = {name: record for name, record, error in results if record}
    errors = {name: error for name, record, error in results if error}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'worlds': records, 'unavailable': errors}, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'available': len(records), 'unavailable': errors}, indent=2))
