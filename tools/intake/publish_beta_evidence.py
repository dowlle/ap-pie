"""Publish public exact-release evidence to the beta container only."""
import argparse
import json
import shlex
import subprocess
from pathlib import Path

REMOTE = r'''
import json,sys,time,os,tempfile
from pathlib import Path
from security_reviews import validate_catalog,load_catalog,record_id
from fuzz_evidence import load_provenance
root=Path('/app/.state')
payload=json.load(sys.stdin)
security=validate_catalog(payload['security'])+load_catalog(root/'security-evidence.json')
security=list({record_id(r):r for r in security}.values())
validate_catalog({'schema':1,'records':security})
existing=load_provenance(str(root/'fuzz-evidence.json'),str(root/'absent.json'),time.time_ns())
fuzz=list({json.dumps(r,sort_keys=True):r for r in payload['fuzz']['records']+existing}.values())
staged=[]
try:
    for name,records in [('security-evidence.json',security),('fuzz-evidence.json',fuzz)]:
        body=(json.dumps({'schema':1,'records':records})+'\n').encode()
        if len(body)>5*1024*1024: raise ValueError('Evidence budget exceeded')
        with tempfile.NamedTemporaryFile(dir=root,prefix=name+'.intake.',delete=False) as out:
            out.write(body);out.flush();os.fsync(out.fileno());p=Path(out.name)
        staged.append((p,root/name))
        if name.startswith('security'): load_catalog(p)
        elif load_provenance(str(p),str(root/'absent.json'),time.time_ns())!=records:
            raise ValueError('Invalid generation evidence')
    for source,target in staged: source.replace(target)
    print(json.dumps({'security_records':len(security),'generation_records':len(fuzz)}))
finally:
    for source,target in staged: source.unlink(missing_ok=True)
'''


def publish(target, security, generation):
    payload = {'security': json.loads(Path(security).read_text()), 'fuzz': json.loads(Path(generation).read_text())}
    # Fixed beta target container makes production publication unavailable.
    remote = shlex.join(['docker', 'exec', '--user', '1000', '-i', 'ap-pie-beta-ap-web-1', 'python', '-c', REMOTE])
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', target, remote],
                            input=json.dumps(payload), text=True, capture_output=True, timeout=90)
    if result.returncode:
        raise RuntimeError('Beta evidence publication failed')
    return json.loads(result.stdout)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ssh-target',required=True)
    p.add_argument('--security',type=Path,required=True)
    p.add_argument('--generation',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(publish(a.ssh_target,a.security,a.generation)))
