"""Upload hash-verified cache bytes before publishing beta discovery metadata."""
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import tarfile

INVENTORY = r'''
import hashlib,json,re
from pathlib import Path
root=Path('/app/.state/discovery-archives');root.mkdir(exist_ok=True)
valid=[]
for p in root.glob('*.apworld'):
    if re.fullmatch('[a-f0-9]{64}.apworld',p.name) and p.stat().st_size<=50*1024*1024:
        with p.open('rb') as source:
            if hashlib.file_digest(source,'sha256').hexdigest()==p.stem:valid.append(p.stem)
print(json.dumps(valid))
'''

INGEST = r'''
import hashlib,json,os,re,sys,tarfile,tempfile
from pathlib import Path
root=Path('/app/.state/discovery-archives');root.mkdir(exist_ok=True)
count=total=0
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as stream:
    for member in stream:
        count+=1;total+=member.size
        if count>10000 or total>50*1024**3 or not member.isfile() or not re.fullmatch('[a-f0-9]{64}.apworld',member.name) or not 0<member.size<=50*1024**2:
            raise ValueError('Invalid archive transfer')
        staged=None
        try:
            checksum=hashlib.sha256();source=stream.extractfile(member)
            with tempfile.NamedTemporaryFile(dir=root,prefix='staged.',delete=False) as output:
                staged=Path(output.name)
                while block:=source.read(65536):checksum.update(block);output.write(block)
                output.flush();os.fsync(output.fileno())
            if checksum.hexdigest()!=member.name[:-8]:raise ValueError('Archive transfer checksum mismatch')
            staged.chmod(0o444);staged.replace(root/member.name)
        finally:
            if staged is not None:staged.unlink(missing_ok=True)
directory=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
try:os.fsync(directory)
finally:os.close(directory)
print(json.dumps({'uploaded_archives':count}))
'''


def command(target, code):
    remote=shlex.join(['docker','exec','--user','1000','-i','ap-pie-beta-ap-web-1','python','-c',code])
    return ['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',target,remote]


def publish(target, snapshot, archives):
    desired={r['sha256'] for r in snapshot['releases']}
    if any(not re.fullmatch('[a-f0-9]{64}',digest) for digest in desired):
        raise ValueError('Invalid archive identity')
    inventory=subprocess.run(command(target,INVENTORY),capture_output=True,text=True,timeout=180,check=True)
    existing=json.loads(inventory.stdout)
    if not isinstance(existing,list) or any(not isinstance(v,str) or not re.fullmatch('[a-f0-9]{64}',v) for v in existing):
        raise ValueError('Invalid remote cache inventory')
    missing=sorted(desired-set(existing))
    if not missing:return {'uploaded_archives':0}
    process=subprocess.Popen(command(target,INGEST),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=process.stdin,mode='w|') as stream:
            for digest in missing:
                path=Path(archives)/(digest+'.apworld')
                with path.open('rb') as source:
                    if hashlib.file_digest(source,'sha256').hexdigest()!=digest:
                        raise ValueError('Local cache checksum mismatch')
                    source.seek(0)
                    member=tarfile.TarInfo(digest+'.apworld');member.size=path.stat().st_size;member.mode=0o444
                    stream.addfile(member,source)
        process.stdin.close();process.stdin=None
        output,error=process.communicate(timeout=900)
        if process.returncode:raise RuntimeError('Beta archive transfer failed')
        return json.loads(output)
    finally:
        if process.poll() is None:
            process.terminate();process.wait(timeout=15)
