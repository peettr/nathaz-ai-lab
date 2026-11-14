#!/usr/bin/env python3
"""Bounded *training-only* throughput probe: 2022-01-01 00 UTC GFS f000..f018.
No holdout observations are loaded. Persist measurement to /content/m4_probe.json.
"""
import json,time,requests
from datetime import datetime,timezone
import eccodes
from concurrent.futures import ThreadPoolExecutor,as_completed
URL='https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.20220101/00/atmos/gfs.t00z.pgrb2.0p25.f{lead:03d}'
S=requests.Session(); S.headers['User-Agent']='R23.2-M4-research-training-probe'
def one(lead):
    start=time.monotonic();url=URL.format(lead=lead)
    r=S.get(url+'.idx',timeout=45);r.raise_for_status();lines=r.text.splitlines()
    entries=[(int(x.split(':')[1]),x.split(':')[3],x.split(':')[4]) for x in lines]
    rows=[]
    for name in ('UGRD','VGRD'):
        i=next(i for i,e in enumerate(entries) if e[1]==name and e[2]=='10 m above ground')
        a=entries[i][0];b=entries[i+1][0]-1
        response=S.get(url,headers={'Range':f'bytes={a}-{b}'},timeout=45)
        response.raise_for_status()
        if response.status_code!=206 or len(response.content)!=b-a+1:raise ValueError(f'bad range: {response.status_code}, {len(response.content)}, {a}-{b}')
        gid=eccodes.codes_new_from_message(response.content)
        try:
            vals=eccodes.codes_get_array(gid,'values');rows.append([name,len(vals),float(vals[0]),len(response.content)])
        finally:eccodes.codes_release(gid)
    return [lead,round(time.monotonic()-start,2),rows]
if __name__=='__main__':
    t=time.monotonic();out=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for f in as_completed([pool.submit(one,i) for i in range(19)]):
            result=f.result();out.append(result);print('GFS_PROBE',result[0],result[1],flush=True)
    data={'init':'2022-01-01T00:00:00Z','count':len(out),'wall_seconds':round(time.monotonic()-t,2),'results':sorted(out),'measured_utc':datetime.now(timezone.utc).isoformat()}
    open('/content/m4_probe.json','w').write(json.dumps(data,indent=2))
    print('PROBE_DONE',data['wall_seconds'],flush=True)
