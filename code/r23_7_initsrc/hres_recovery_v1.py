#!/usr/bin/env python3
"""Retry only unsuccessful 2023 HRES cycles, preserving every original ledger."""
import json,time,sys
from pathlib import Path
import pandas as pd,numpy as np
sys.path.insert(0,'/content/r237_m2')
import hres_2023_v2 as h
R=Path('/content/r237_m2')
old=json.loads((R/'HRES_remainder_ledger_v1.json').read_text())['ledger']
failed=[pd.Timestamp(x['init_utc']) for x in old if x['status']!='ok']
assert len(old)==668 and len(failed)==95
stations=pd.read_csv(R/'stations.csv');rows=[];ledger=[];start=time.monotonic();meta=None
for n,init in enumerate(failed,1):
    entry={'init_utc':init.isoformat(),'source':'HRES_OpenData_0p4-beta','urls':[],'range_bytes':0}
    t=time.monotonic()
    try:
        bylead={}
        for lead in (24,48):
            url=h.url(init,lead);entry['urls'].append(url)
            records=[json.loads(x) for x in h.get(url.replace('.grib2','.index')).text.splitlines()]
            pair={x['param']:x for x in records if x.get('param') in ('10u','10v') and x.get('levtype')=='sfc'}
            assert set(pair)=={'10u','10v'}
            vectors=[]
            for param in ('10u','10v'):
                item=pair[param];pos=int(item['_offset']);length=int(item['_length'])
                r=h.get(url,{'Range':f'bytes={pos}-{pos+length-1}'})
                assert len(r.content)==length
                values,metadata=h.sample(r.content,stations)
                assert metadata['name']==param
                vectors.append(values);entry['range_bytes']+=length
                if meta is None:meta=metadata
            bylead[lead]=vectors
        for lead in (24,48):
            u,v=bylead[lead]
            for s,uu,vv in zip(stations.station,u,v):rows.append((s,init.isoformat(),lead,'HRES',uu,vv,np.nan,np.nan))
        entry.update(status='ok',station_rows=24)
    except Exception as exc:
        entry.update(status='missing' if '404' in str(exc) else 'error',error=repr(exc))
        print('RECOVERY_ERROR',init.isoformat(),repr(exc),flush=True)
    entry['seconds']=time.monotonic()-t;ledger.append(entry)
    if n%10==0:print('RECOVERY_PROGRESS',n,len(failed),sum(x['status']=='ok' for x in ledger),time.monotonic()-start,flush=True)
summary={'stage':'remainder_recovery','expected':len(failed),'ok':sum(x['status']=='ok' for x in ledger),'missing':sum(x['status']=='missing' for x in ledger),'error':sum(x['status']=='error' for x in ledger),'wall_seconds':time.monotonic()-start,'grid':meta,'variable_names':['10u','10v'],'lead_hours':[24,48],'ledger':ledger}
with (R/'HRES_remainder_recovery_ledger_v1.json').open('x') as f:json.dump(summary,f,indent=2)
with (R/'HRES_remainder_recovery_station_v1.csv.gz').open('xb') as f:pd.DataFrame(rows,columns=h.COLS).to_csv(f,index=False,compression='gzip')
print('RECOVERY_DONE',summary['ok'],summary['missing'],summary['error'],summary['wall_seconds'],flush=True)
