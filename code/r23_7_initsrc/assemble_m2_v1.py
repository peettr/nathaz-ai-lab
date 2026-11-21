#!/usr/bin/env python3
"""Combine immutable HRES receipts, audit source cycles and exclusions."""
import csv,gzip,json,datetime,collections,hashlib
from pathlib import Path
R=Path(__file__).resolve().parent;M=R/'m2_2023_v1';O=M/'assembled_v1';O.mkdir(exist_ok=True)
items=[(M/'HRES_pilot_station_v1.csv.gz',M/'HRES_pilot_ledger_v1.json'),(M/'HRES_pilot_recovery_station_v1.csv.gz',M/'HRES_pilot_recovery_ledger_v1.json'),(M/'HRES_remainder_station_v1.csv.gz',M/'HRES_remainder_ledger_v1.json'),(M/'recovery_final_v1/HRES_remainder_recovery_station_v1.csv.gz',M/'recovery_final_v1/HRES_remainder_recovery_ledger_v1.json'),(M/'HRES_transient_retry_station_v1.csv.gz',M/'HRES_transient_retry_ledger_v1.json')]
rows={};hist=collections.defaultdict(list);heads=set();hashes={}
for data,ledger in items:
    hashes[str(data.relative_to(R))]=hashlib.sha256(data.read_bytes()).hexdigest()
    with gzip.open(data,'rt') as f:
        c=csv.DictReader(f);heads.add(tuple(c.fieldnames))
        for x in c:
            k=(x['station'],x['init_utc'],x['lead_h']);assert k not in rows,(data,k)
            rows[k]=x
    d=json.loads(ledger.read_text())
    for x in d['ledger']:hist[x['init_utc']].append({'stage':str(ledger.relative_to(R)),'status':x['status'],'error':x.get('error')})
assert len(heads)==1
start=datetime.datetime(2023,1,18,tzinfo=datetime.timezone.utc)
expected=[(start+datetime.timedelta(hours=12*i)).isoformat() for i in range(696)]
assert set(hist)==set(expected),(len(hist),len(expected))
final={k:v[-1] for k,v in hist.items()}
ok={k for k,v in final.items() if v['status']=='ok'}
assert len(rows)==len(ok)*24,(len(rows),len(ok))
assert {x['init_utc'] for x in rows.values()}==ok
out=O/'HRES_2023_station_assembled_v1.csv.gz'
with out.open('xb') as raw:
    with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as z:
        with __import__('io').TextIOWrapper(z,encoding='utf8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(next(iter(heads))));w.writeheader();w.writerows(rows[k] for k in sorted(rows))
report={'expected':len(expected),'ok':len(ok),'missing_or_error':{k:v for k,v in final.items() if k not in ok},'source_histories':dict(hist),'station_rows':len(rows),'input_sha256':hashes,'output_sha256':hashlib.sha256(out.read_bytes()).hexdigest()}
with (O/'HRES_2023_assembly_audit_v1.json').open('x') as f:json.dump(report,f,indent=2)
print('HRES',report['ok'],'/',report['expected'],'rows',len(rows),'excluded',len(report['missing_or_error']))
print('missing_or_error',[(k,v['status']) for k,v in report['missing_or_error'].items()])
