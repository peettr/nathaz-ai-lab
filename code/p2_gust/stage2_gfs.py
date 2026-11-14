#!/usr/bin/env python3
"""GFS 0.25° station extraction with M5 height features, no error/skill calculation."""
import csv,datetime as dt,hashlib,json,math,os,sys,time,traceback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import numpy as np,requests,eccodes
R=Path('/content/p1');LEADS=(24,30,36,42,48);PREV={24:23,30:29,36:35,42:41,48:45}
LEVELS=(1000,975,950,925,900,850,800,750,700,650,600,550,500)
BASE='https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{day}/{hh}/atmos/gfs.t{hh}z.pgrb2.0p25.f{fhr:03d}'
FIELDS=[('UGRD','10 m above ground'),('VGRD','10 m above ground'),('HGT','surface')]+[(v,f'{p} mb') for p in LEVELS for v in ('UGRD','VGRD','HGT')]

def req(url,headers=None):
    for n in range(3):
        try:
            r=requests.get(url,headers={'User-Agent':'R23.2d P1 blind GFS fetch',**(headers or {})},timeout=(15,65))
            if r.status_code in (200,206,404,403):return r
            if r.status_code not in (429,500,502,503,504):return r
        except requests.RequestException:
            if n==2:raise
        time.sleep(n+1)
    return r

def hour(init,h,stations):
    url=BASE.format(day=init.strftime('%Y%m%d'),hh=init.strftime('%H'),fhr=h)
    resp=req(url+'.idx');resp.raise_for_status()
    idx=[line.split(':') for line in resp.text.splitlines()]
    positions={(x[3],x[4]):i for i,x in enumerate(idx) if len(x)>4}
    wanted=FIELDS+([('GUST','surface')] if h in LEADS else [])
    missing=set(wanted)-set(positions)
    if missing:raise ValueError(f'missing {url} {missing}')
    def field(pair):
        pos=positions[pair];lo=int(idx[pos][1]);hi=int(idx[pos+1][1])-1
        response=req(url,{'Range':f'bytes={lo}-{hi}'})
        if response.status_code!=206 or len(response.content)!=hi-lo+1:raise RuntimeError(f'range failure {url} {pair} {response.status_code} bytes {len(response.content)} expected {hi-lo+1}')
        gid=eccodes.codes_new_from_message(response.content)
        try:
            if eccodes.codes_get(gid,'Ni')!=1440 or eccodes.codes_get(gid,'Nj')!=721 or eccodes.codes_get(gid,'latitudeOfFirstGridPointInDegrees')!=90:raise ValueError('unexpected GFS grid')
            arr=eccodes.codes_get_array(gid,'values').reshape(721,1440)
            vals=[]
            for s in stations:
                y=(90-float(s['lat']))*4;x=(float(s['lon'])%360)*4;i=int(y);j=int(x);a=y-i;b=x-j
                vals.append(float((1-a)*(1-b)*arr[i,j]+a*(1-b)*arr[i+1,j]+(1-a)*b*arr[i,j+1]+a*b*arr[i+1,j+1]))
            return pair,vals
        finally:eccodes.codes_release(gid)
    with ThreadPoolExecutor(max_workers=14) as pool:data=dict(pool.map(field,wanted))
    return data,url

def m5_features(low,high,alpha,stations):
    fields={key:np.asarray(low[key])*(1-alpha)+np.asarray(high[key])*alpha for key in FIELDS}
    out=[]
    for i,s in enumerate(stations):
        zsurf=fields['HGT','surface'][i];zs=float(s['elevation_m'])
        layers=[]
        for p in LEVELS:
            z=fields['HGT',f'{p} mb'][i];u=fields['UGRD',f'{p} mb'][i];v=fields['VGRD',f'{p} mb'][i]
            if np.isfinite(z) and np.isfinite(u) and np.isfinite(v) and z>=zsurf:layers.append((z,u,v))
        layers.sort()
        if zs<=zsurf:eu,ev=fields['UGRD','10 m above ground'][i],fields['VGRD','10 m above ground'][i]
        elif not layers:raise ValueError('no above-ground pressure layer '+s['station'])
        else:
            anchors=[(zsurf+10,fields['UGRD','10 m above ground'][i],fields['VGRD','10 m above ground'][i])]+[x for x in layers if x[0]>zsurf+10]
            if zs<=anchors[0][0]:eu,ev=anchors[0][1:]
            elif zs>=anchors[-1][0]:raise ValueError('site above 500 hPa '+s['station'])
            else:
                j=next(j for j in range(1,len(anchors)) if anchors[j][0]>=zs)
                bot,top=anchors[j-1],anchors[j];b=(zs-bot[0])/(top[0]-bot[0]);eu=bot[1]*(1-b)+top[1]*b;ev=bot[2]*(1-b)+top[2]*b
        out.append((math.hypot(eu,ev),float(zsurf),float(zs-zsurf)))
    return out

def work(t,stations):
    stamp=t.strftime('%Y%m%d%H');dest=R/'forecast_parts'/f'GFS_{stamp}.csv';manifest=dest.with_suffix('.json')
    if dest.exists() and manifest.exists():return 'skip',stamp,0
    if dest.exists() or manifest.exists():return 'incomplete_existing',stamp,0
    began=time.monotonic()
    try:
        fhrs=sorted(set(LEADS)|set(PREV.values()))
        with ThreadPoolExecutor(max_workers=5) as pool:
            fs={pool.submit(hour,t,h,stations):h for h in fhrs}
            all_hours={fs[f]:f.result()[0] for f in as_completed(fs)}
        rows=[]
        for lead in LEADS:
            # Same M5 fhr-5min vector interpolation, then altitude interpolation.
            a=(lead-1/12-PREV[lead])/(lead-PREV[lead]);features=m5_features(all_hours[PREV[lead]],all_hours[lead],a,stations)
            now=all_hours[lead]
            for j,s in enumerate(stations):
                rows.append((s['station'],t.isoformat()+'Z',lead,'GFS',now['UGRD','10 m above ground'][j],now['VGRD','10 m above ground'][j],now['GUST','surface'][j],*features[j],BASE.format(day=t.strftime('%Y%m%d'),hh=t.strftime('%H'),fhr=lead)))
        with dest.open('x',newline='') as o:
            w=csv.writer(o);w.writerow(['station','init_utc','lead_h','source','fc_u10','fc_v10','fc_gust','m5_v1','m5_z_model_sfc','m5_dz','object_url']);w.writerows(rows)
        manifest.write_text(json.dumps({'source':'GFS','init':stamp,'rows':len(rows),'seconds':time.monotonic()-began,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}))
        return 'ok',stamp,round(time.monotonic()-began,2)
    except Exception:return 'error',stamp,traceback.format_exc()[-2500:]

def main():
    p=R/'stations_p2_frozen.csv';m=json.loads((R/'freeze_manifest.json').read_text())
    assert hashlib.sha256(p.read_bytes()).hexdigest()==m['station_sha256']
    stations=list(csv.DictReader(p.open()));(R/'forecast_parts').mkdir(exist_ok=True)
    todo=[]
    for a,b in [('2022-10-01','2023-04-01'),('2023-10-01','2024-04-01'),('2024-10-01','2025-04-01')]:
        t=dt.datetime.fromisoformat(a);end=dt.datetime.fromisoformat(b)
        while t<end:todo.append(t);t+=dt.timedelta(hours=12)
    if os.environ.get('P1_PILOT')=='1':todo=todo[:1]
    with ThreadPoolExecutor(max_workers=2) as pool:
        fs=[pool.submit(work,t,stations) for t in todo]
        for n,f in enumerate(as_completed(fs),1):
            status,stamp,elapsed=f.result()
            with (R/'gfs_progress.jsonl').open('a') as o:o.write(json.dumps({'status':status,'init':stamp,'seconds_or_error':elapsed})+'\n')
            print('GFS',n,len(todo),status,stamp,str(elapsed)[:400],flush=True)
    print('GFS_STAGE_DONE',len(todo),flush=True)
if __name__=='__main__':main()
