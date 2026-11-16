"""Run static schema extraction without network, home or credentials."""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from ledger import Ledger


def run(archive, module, digest):
    root=Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory() as tmp:
        job=Path(tmp)/'job.json'
        job.write_text(json.dumps({'module':module,'sha256':digest}))
        args=['/usr/bin/bwrap','--die-with-parent','--new-session','--unshare-all','--clearenv',
              '--ro-bind','/usr','/usr','--ro-bind','/lib','/lib','--ro-bind','/lib64','/lib64',
              '--proc','/proc','--dev','/dev','--tmpfs','/tmp','--dir','/parser',
              '--ro-bind',str(root/'ap-web/apworld_options_parser.py'),'/parser/apworld_options_parser.py',
              '--ro-bind',str(Path(__file__).with_name('artifact_worker.py')),'/parser/artifact_worker.py',
              '--ro-bind',str(Path(__file__).with_name('schema_worker.py')),'/worker.py',
              '--ro-bind',str(job),'/job.json','--ro-bind',str(archive.resolve()),'/archive.apworld',
              '--chdir','/tmp','/usr/bin/python3','-I','/worker.py']
        process=subprocess.run(args,capture_output=True,text=True,timeout=45,env={'PATH':'/usr/bin:/bin'})
        if process.returncode:
            raise RuntimeError('Restricted schema worker failed')
        if len(process.stdout.encode())>2*1024*1024:
            raise ValueError('Schema output too large')
        result=json.loads(process.stdout)
        if result.get('sha256')!=digest or not isinstance(result.get('schema'),(dict,type(None))):
            raise ValueError('Invalid schema worker output')
        return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--module',required=True)
    p.add_argument('--sha256',required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    result=run(a.archive,a.module,a.sha256)
    a.out.write_text(json.dumps(result)+'\n')
    print(json.dumps({'sha256':a.sha256,'derivable':result['schema'] is not None}))
