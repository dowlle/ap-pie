"""Export only completed, hash-matched restricted schema results."""
import argparse
import json
from pathlib import Path
from ledger import Ledger
from snapshot import write_atomic


def export(ledger):
    records={}
    for row in ledger.db.execute("SELECT jobs.release_id,jobs.result,releases.sha256 FROM jobs JOIN releases ON releases.id=jobs.release_id WHERE kind='schema' AND state='completed'"):
        result=json.loads(row['result'])
        if result.get('sha256')!=row['sha256'] or not isinstance(result.get('schema'),(dict,type(None))):
            raise ValueError('Stored schema result does not match release')
        records[row['release_id']]=result
    return {'schema':1,'records':records}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    ledger=Ledger(a.db)
    try:
        write_atomic(a.out,export(ledger))
    finally:
        ledger.db.close()
