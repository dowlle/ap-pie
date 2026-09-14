"""Static schema extraction from verified bytes in a restricted subprocess."""
import hashlib
import json
import resource
import sys
from pathlib import Path


def main():
    resource.setrlimit(resource.RLIMIT_AS, (512*1024*1024,)*2)
    resource.setrlimit(resource.RLIMIT_CPU, (30,)*2)
    sys.path.insert(0, '/parser')
    from apworld_options_parser import parse_apworld_options_bytes
    from artifact_worker import inspect_archive
    job=json.loads(Path('/job.json').read_text())
    data=Path('/archive.apworld').read_bytes()
    if hashlib.sha256(data).hexdigest()!=job['sha256']:
        raise ValueError('Schema artifact checksum mismatch')
    inspect_archive(Path('/archive.apworld'))
    schema=parse_apworld_options_bytes(data,stem_hint=job['module'])
    result={'sha256':job['sha256'],'schema':schema}
    body=json.dumps(result)
    if len(body.encode())>2*1024*1024:
        raise ValueError('Schema output budget exceeded')
    print(body)


if __name__=='__main__':
    main()
