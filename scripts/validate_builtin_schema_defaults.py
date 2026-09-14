"""Validate frozen defaults against a clean official release source checkout."""
import json
import sys
from pathlib import Path

source = Path(sys.argv[1])
sys.path.insert(0, str(source))
import worlds
from worlds.AutoWorld import AutoWorldRegister

records = json.loads(Path(sys.argv[2]).read_text())['worlds']
errors = {}
count = 0
for key, record in records.items():
    world = AutoWorldRegister.world_types.get(record['game'])
    if not world:
        errors[key] = 'game not registered by official release'
        continue
    types = world.options_dataclass.type_hints
    for option in record['schema']['options']:
        try:
            types[option['name']].from_any(option['default'])
            count += 1
        except Exception as error:
            errors[key + '/' + option['name']] = str(error)
print(json.dumps({'games': len(records), 'validated_defaults': count, 'errors': errors}, indent=2))
sys.exit(bool(errors))
