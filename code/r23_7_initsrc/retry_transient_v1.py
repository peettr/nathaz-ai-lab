#!/usr/bin/env python3
"""Retry only unresolved transient AI/HRES objects, immutable evidence."""
import json,time,sys
from pathlib import Path
import pandas as pd,numpy as np
R=Path('/content/r237_m2');sys.path.insert(0,str(R))
import run_forecasts as ai
import hres_2023_v2 as h
ai.LEADS=(24,48)
cols=['station','init_utc','lead_h','source','fc_u','fc_v','fc_u100','fc_v100']
stations=pd.read_csv(R/'stations.csv')
for label,filename in [('PANG_v100_IFS','PANG_v100_IFS_ledger_v1.json'),('HRES','HRES_remainder_recovery_ledger_v1.json')]:
    prev=json.loads((R/filename).read_text())['ledger']
    failed=[pd.Timestamp(e['init_utc']) for e in prev if e['status']=='error']
    rows=[];ledger=[];start=time.monotonic()
    for init in failed:
        ent={'init_utc':init.isoformat(),'source':label};t=time.monotonic()
        try:
            if label!='HRES':
                rr,_,size=ai.ai(init,label,stations)
                assert len(rr)==24
                rows.extend(rr);ent.update(status='ok',object_size=size)
            else:
                bylead={}
                for lead in (24,48):
                    url=h.url(init,lead)
                    rec=[json.loads(x) for x in h.get(url.replace('.grib2','.index')).text.splitlines()]
                    pair={x['param']:x for x in rec if x.get('param') in ('10u','10v') and x.get('levtype')=='sfc'}
                    assert set(pair)=={'10u','10v'}
                    vec=[]
                    for param in ('10u','10v'):
                        e=pair[param];off=int(e['_offset']);length=int(e['_length'])
                        resp=h.get(url,{'Range':f'bytes={off}-{off+length-1}'})
                        assert len(resp.content)==length
                        v,meta=h.sample(resp.content,stations)
                        assert meta['name']==param
                        vec.append(v)
                    bylead[lead]=vec
                for lead,(uu,vv) in bylead.items():
                    rows.extend((s,init.isoformat(),lead,'HRES',u,v,np.nan,np.nan) for s,u,v in zip(stations.station,uu,vv))
                ent['status']='ok'
        except Exception as exc:
            ent.update(status='missing' if '404' in str(exc) else 'error',error=repr(exc))
        ent['seconds']=time.monotonic()-t;ledger.append(ent)
        print(label,init.isoformat(),ent['status'],ent['seconds'],flush=True)
    output={'expected':len(failed),'ok':sum(x['status']=='ok' for x in ledger),'missing':sum(x['status']=='missing' for x in ledger),'error':sum(x['status']=='error' for x in ledger),'wall_seconds':time.monotonic()-start,'ledger':ledger}
    with (R/f'{label}_transient_retry_ledger_v1.json').open('x') as f:json.dump(output,f,indent=2)
    with (R/f'{label}_transient_retry_station_v1.csv.gz').open('xb') as f:pd.DataFrame(rows,columns=cols).to_csv(f,index=False,compression='gzip')
    print('FINISHED',label,output['ok'],output['missing'],output['error'],flush=True)
