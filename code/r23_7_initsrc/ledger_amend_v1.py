#!/usr/bin/env python3
"""Preserve raw collector statuses; classify S3 FileNotFoundError as missing in amended ledger."""
import json,pathlib,collections
root=pathlib.Path(__file__).parent
src=root/'second_source_v1/PANG_v100_IFS_ledger_v1.json'
d=json.loads(src.read_text())
assert d['ok']+d['missing']+d['error']==d['expected_objects']==360
for row in d['ledger']:
    if row['status']=='error' and row.get('error','').startswith('FileNotFoundError('):
        row['status']='missing'
d['status_amendment']='v1 collector misclassified fsspec FileNotFoundError as error; v2 classifies absent source object as missing, no replacement'
c=collections.Counter(x['status'] for x in d['ledger'])
for k in ('ok','missing','error'):d[k]=c[k]
out=root/'second_source_v1/PANG_v100_IFS_ledger_v2.json'
with out.open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2)
print({k:v for k,v in d.items() if k!='ledger'})
print('missing list',[(x['init_utc'],x.get('url')) for x in d['ledger'] if x['status']=='missing'])
