"""Register reviewed source submissions without granting security clearance."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit
from ledger import Ledger, MODULE


def register(ledger, records):
    if not isinstance(records,list) or len(records)>1000:
        raise ValueError('Invalid source registry')
    # Validate the entire batch before any database mutation.
    for r in records:
        if not isinstance(r,dict) or set(r)-{'module','name','url','version','setup_guide'}:
            raise ValueError('Invalid submitted source fields')
        if not isinstance(r.get('module'),str) or not MODULE.fullmatch(r['module']) or r['module'] in ('.','..'):
            raise ValueError('Invalid submitted module')
        if not isinstance(r.get('name'),str) or not 0<len(r['name'])<=300:
            raise ValueError('Invalid submitted game name')
        u=urlsplit(r.get('url',''))
        if u.scheme!='https' or u.hostname!='github.com' or u.username or u.password or u.query or u.fragment or u.port not in (None,443) or '/releases/download/' not in u.path or not u.path.endswith('.apworld'):
            raise ValueError('Invalid submitted artifact')
        if not isinstance(r.get('version'),str) or not 0<len(r['version'])<=200:
            raise ValueError('Invalid submitted version')
        guide=r.get('setup_guide')
        if guide is not None and (not isinstance(guide,str) or urlsplit(guide).scheme!='https'):
            raise ValueError('Invalid submitted guide')
    with ledger.db:
        for r in records:
            ledger.register(r['module'],{'name':r['name'],'home':r['url'].split('/releases/download/')[0],
                                         'setup_guide':r.get('setup_guide')})
            ledger.discover(r['module'],r['version'],r['url'],origin='source-submission')
    return len(records)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',type=Path,required=True)
    p.add_argument('--submissions',type=Path,required=True)
    a=p.parse_args()
    ledger=Ledger(a.db)
    try:
        print(json.dumps({'registered':register(ledger,json.loads(a.submissions.read_text()))}))
    finally:
        ledger.db.close()
