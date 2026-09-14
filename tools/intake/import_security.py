"""Reuse existing immutable public security evidence for exact release bytes."""
import argparse
import json
import sys
from pathlib import Path
from ledger import Ledger
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ap-web'))
from security_reviews import validate_catalog


def process(ledger, records, *, limit=20):
    # Validate the entire batch before claiming or changing any queue job.
    records = validate_catalog({'schema': 1, 'records': records})
    lookup={}
    for r in records:
        key=(r.get('module'),r.get('version'),r.get('sha256'))
        lookup.setdefault(key,[]).append(r)
    completed=0
    for _ in range(limit):
        job=ledger.claim('security')
        if job is None:break
        release=dict(ledger.db.execute('SELECT * FROM releases WHERE id=?',(job['release_id'],)).fetchone())
        matching=lookup.get((release['module'],release['version'],release['sha256']),[])
        if not matching:
            ledger.finish(release['id'],'security',job['token'],None,error='Source review required')
            continue
        # Preserve all matching immutable results; never collapse a hold or
        # concern into a more recent automatic PASS here.
        public=[dict(r) for r in matching]
        ledger.finish(release['id'],'security',job['token'],{'records':public})
        completed+=1
    return completed


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',type=Path,required=True)
    p.add_argument('--evidence',type=Path,required=True)
    p.add_argument('--limit',type=int,default=20)
    a=p.parse_args()
    payload=json.loads(a.evidence.read_text())
    records=payload['records'] if isinstance(payload,dict) else payload
    l=Ledger(a.db)
    try:print(json.dumps({'completed':process(l,records,limit=a.limit),'queue':l.status()}))
    finally:l.db.close()
