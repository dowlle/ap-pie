"""Validate and publish discovery metadata to the fixed beta container."""
import argparse
import json
import shlex
import subprocess
from pathlib import Path

REMOTE = r'''
import json,sys,os,tempfile
from pathlib import Path
import discovery
root=Path('/app/.state')
body=sys.stdin.buffer.read(5*1024*1024+1)
if len(body)>5*1024*1024:raise ValueError('Discovery budget exceeded')
p=None
try:
    with tempfile.NamedTemporaryFile(dir=root,prefix='discovery.intake.',delete=False) as out:
        out.write(body);out.flush();os.fsync(out.fileno());p=Path(out.name)
    data=discovery.load(p)
    p.replace(root/'discovery.json')
    print(json.dumps({'available_releases':len(data['releases'])}))
finally:
    if p is not None:p.unlink(missing_ok=True)
'''


def publish(target, path):
    body = Path(path).read_bytes()
    if len(body) > 5 * 1024 * 1024:
        raise ValueError('Discovery budget exceeded')
    remote = shlex.join(['docker', 'exec', '--user', '1000', '-i', 'ap-pie-beta-ap-web-1', 'python', '-c', REMOTE])
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', target, remote],
                            input=body, capture_output=True, timeout=90)
    if result.returncode:
        raise RuntimeError('Beta discovery publication failed')
    return json.loads(result.stdout)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ssh-target',required=True)
    p.add_argument('--snapshot',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(publish(a.ssh_target,a.snapshot)))
