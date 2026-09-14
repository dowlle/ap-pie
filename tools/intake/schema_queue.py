"""Claim immutable schema jobs and retain restricted-worker output durably."""
import argparse
import json
from pathlib import Path
from ledger import Ledger
from run_schema import run


def process(ledger, archives, *, limit=5):
    completed=0
    for _ in range(limit):
        job=ledger.claim('schema',lease_seconds=120)
        if job is None:
            break
        release=dict(ledger.db.execute('SELECT * FROM releases WHERE id=?',(job['release_id'],)).fetchone())
        try:
            result=run(archives/(release['sha256']+'.apworld'),release['module'],release['sha256'])
        except Exception as e:
            ledger.finish(release['id'],'schema',job['token'],None,error=type(e).__name__)
        else:
            ledger.finish(release['id'],'schema',job['token'],result)
            completed+=1
    return completed


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',type=Path,required=True)
    p.add_argument('--archives',type=Path,required=True)
    p.add_argument('--limit',type=int,default=5)
    a=p.parse_args()
    ledger=Ledger(a.db)
    try:
        print(json.dumps({'completed':process(ledger,a.archives,limit=a.limit),'queue':ledger.status()}))
    finally:
        ledger.db.close()
