#!/usr/bin/env python3
"""Blind station×init×lead join; requires six complete interval-end 10-minute observations."""
import csv,json,hashlib,datetime as dt,collections
from pathlib import Path
R=Path('/content/p1');SEASONS=[('2022-10-01','2023-04-01'),('2023-10-01','2024-04-01'),('2024-10-01','2025-04-01')];LEADS=(24,30,36,42,48)
SOURCES=('FOUR_v200_GFS','GRAP_v100_GFS','PANG_v100_GFS','GFS')

def main():
    p=R/'stations_p2_frozen.csv';m=json.loads((R/'freeze_manifest.json').read_text());assert hashlib.sha256(p.read_bytes()).hexdigest()==m['station_sha256']
    stations=list(csv.DictReader(p.open()));assert len(stations)==m['selected']
    obs={};coverage={};missing=collections.Counter()
    inits=[]
    for a,b in SEASONS:
        t=dt.datetime.fromisoformat(a);end=dt.datetime.fromisoformat(b)
        while t<end:inits.append(t);t+=dt.timedelta(hours=12)
    valid_times={t+dt.timedelta(hours=h) for t in inits for h in LEADS}
    def valid_season(t):return next((i for i,(a,b) in enumerate(SEASONS) if a<=t.date().isoformat()<b),None)
    valid_times={t for t in valid_times if valid_season(t) is not None}
    for s in stations:
        sid=s['station'];data={}
        with (R/'obs'/f'{sid}.csv').open() as f:
            for row in csv.DictReader(f):data[dt.datetime.fromisoformat(row['time_utc'].removesuffix('Z'))]=row
        for t in valid_times:
            times=[t+dt.timedelta(minutes=x) for x in (-20,-10,0,10,20,30)]
            rows=[data.get(x) for x in times]
            if any(r is None or not r['fkl010z0'] or not r['fkl010z1'] for r in rows):continue
            obs[sid,t]=(sum(float(r['fkl010z0']) for r in rows)/6,max(float(r['fkl010z1']) for r in rows),max([float(r['fkl010z3']) for r in rows if r['fkl010z3']],default=None))
        for i in range(3):
            coverage[sid,i]=sum(valid_season(t)==i for key,t in obs if key==sid)
    forecasts={};counts=collections.Counter()
    for src in SOURCES:
        for t in inits:
            stamp=t.strftime('%Y%m%d%H');file=R/'forecast_parts'/f'{src}_{stamp}.csv';manifest=file.with_suffix('.json')
            if not file.exists() or not manifest.exists():missing[src,'missing_object']+=1;continue
            digest=hashlib.sha256(file.read_bytes()).hexdigest()
            meta=json.loads(manifest.read_text());assert digest==meta['sha256']
            with file.open() as f:
                for row in csv.DictReader(f):
                    key=(src,row['station'],t,int(row['lead_h']))
                    assert key not in forecasts
                    forecasts[key]=row;counts[src]+=1
    output=R/'pairs_p2.csv'
    assert not output.exists()
    with output.open('x',newline='') as f:
        fields=['station','terrain','season','source','init_utc','lead_h','valid_end_utc','obs_6x10min_complete','obs_mean_ms','obs_gust_1s_ms','obs_gust_3s_ms','fc_u10_ms','fc_v10_ms','fc_u100_ms','fc_v100_ms','fc_gust_ms','m5_v1_ms','m5_z_model_sfc_m','m5_delta_z_m','forecast_object_url']
        w=csv.writer(f);w.writerow(fields)
        for t in inits:
            for lead in LEADS:
                v=t+dt.timedelta(hours=lead);season=valid_season(v)
                if season is None:continue
                for s in stations:
                    sid=s['station'];ob=obs.get((sid,v))
                    for src in SOURCES:
                        row=forecasts.get((src,sid,t,lead))
                        w.writerow([sid,s['terrain'],season+1,src,t.isoformat()+'Z',lead,v.isoformat()+'Z',int(ob is not None),*(ob if ob else ('','','')),*(row.get(k,'') for k in ['fc_u10','fc_v10','fc_u100','fc_v100','fc_gust','m5_v1','m5_z_model_sfc','m5_dz','object_url'])] if row else [sid,s['terrain'],season+1,src,t.isoformat()+'Z',lead,v.isoformat()+'Z',int(ob is not None),*(ob if ob else ('','','')), *(['']*9)])
    result={'station_sha256':m['station_sha256'],'pairs_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'pairs_bytes':output.stat().st_size,'forecast_rows':dict(counts),'missing_object_counts':{str(k):v for k,v in missing.items()},'obs_six_complete_station_season':{f'{k[0]}:{k[1]+1}':v for k,v in coverage.items()},'expected_sources':list(SOURCES)}
    (R/'pair_manifest.json').write_text(json.dumps(result,indent=2))
    print('PAIRS_DONE',json.dumps(result)[:1300],flush=True)
if __name__=='__main__':main()
