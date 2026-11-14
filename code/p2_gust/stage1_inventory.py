#!/usr/bin/env python3
"""Blind source availability and Swiss station inventory. Never reads forecasts' values."""
import csv, io, json, datetime as dt, hashlib, os, time, traceback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from zoneinfo import ZoneInfo
import requests
ROOT=Path('/content/p1'); ROOT.mkdir(exist_ok=True)
BASE='https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/'
SEASONS=[('2022-10-01','2023-04-01'),('2023-10-01','2024-04-01'),('2024-10-01','2025-04-01')]
OLD={'CHA':'ridge','NAP':'ridge','DOL':'ridge','BEH':'pass','CDM':'pass','GSB':'pass','BLA':'valley','GOS':'valley','ROB':'valley','BUF':'plateau','SAM':'plateau','BRL':'plateau'}
# Exact exposure translations plus separately labeled geomorphologic proxies.
EXPOSURE={'crest':'ridge','pass':'pass','valley':'valley','basin':'valley','height (30-100 m above valley)':'plateau','plain':'plain'}
PARAMS=('fkl010z0','fkl010z1','fkl010z3')

def get(url,method='GET'):
    for n in range(3):
        try:
            r=requests.request(method,url,timeout=(15,120) if method=='GET' else (10,20),headers={'User-Agent':'R23.2d P1 blind inventory research'})
            if r.status_code in (200,404,403):return r
            if r.status_code not in (429,500,502,503,504):return r
        except requests.RequestException:
            if n==2:raise
        time.sleep(1+n*2)
    return r

def fetch_station(record):
    sid=record['station_abbr']; path=ROOT/'obs'/f'{sid}.csv'; stat=ROOT/'inventory'/f'{sid}.json'
    if path.exists() and stat.exists():return json.loads(stat.read_text())
    url=f'{BASE}{sid.lower()}/ogd-smn_{sid.lower()}_t_historical_2020-2029.csv'
    result={'station':sid,'url':url,'exposure':record['station_exposition_en']}
    try:
        r=get(url); result['http']=r.status_code
        if r.status_code!=200:raise RuntimeError(f'HTTP {r.status_code}')
        reader=csv.DictReader(io.StringIO(decode_source(r.content)),delimiter=';')
        if not {'reference_timestamp',*PARAMS}.issubset(reader.fieldnames):raise RuntimeError(f'fields {reader.fieldnames}')
        counts=[Counter() for _ in SEASONS]; seen=set(); rows=[]
        for x in reader:
            stamp=x['reference_timestamp']
            try:t=dt.datetime.strptime(stamp,'%d.%m.%Y %H:%M')
            except ValueError:continue
            ix=next((i for i,(a,b) in enumerate(SEASONS) if a<=t.strftime('%Y-%m-%d')<b),None)
            if ix is None:continue
            key=t.isoformat(timespec='minutes')+'Z'
            if key in seen:raise ValueError(f'duplicate timestamp {sid} {key}')
            seen.add(key);counts[ix]['rows']+=1
            for p in PARAMS:
                if x[p].strip():counts[ix][p]+=1
            rows.append((sid,key,*[x[p] for p in PARAMS]))
        expected=[int((dt.date.fromisoformat(b)-dt.date.fromisoformat(a)).days*144) for a,b in SEASONS]
        result.update(counts=[dict(c) for c in counts],expected=expected,download_bytes=len(r.content),raw_sha256=hashlib.sha256(r.content).hexdigest())
        path.parent.mkdir(exist_ok=True)
        with path.open('x',newline='') as f:
            w=csv.writer(f);w.writerow(['station','time_utc',*PARAMS]);w.writerows(rows)
        result['extracted_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        result['extracted_rows']=len(rows)
    except Exception as e:result['error']=repr(e);result['traceback']=traceback.format_exc()
    stat.parent.mkdir(exist_ok=True);stat.write_text(json.dumps(result,ensure_ascii=False))
    print('SITE',sid,'/'.join(str(c.get('fkl010z0',0)) for c in result.get('counts',[])),result.get('error','OK'),flush=True)
    return result

def archive_one(source,t):
    url=f'https://noaa-oar-mlwp-data.s3.amazonaws.com/{source}/{t:%Y}/{t:%m%d}/{source}_{t:%Y%m%d%H}_f000_f240_06.nc'
    try:
        r=get(url,'HEAD');return {'source':source,'init_utc':t.isoformat()+'Z','status':r.status_code,'bytes':r.headers.get('Content-Length'),'url':url}
    except Exception as e:return {'source':source,'init_utc':t.isoformat()+'Z','error':str(e),'url':url}

def decode_source(data):
    try:return data.decode('utf-8-sig')
    except UnicodeDecodeError:return data.decode('latin-1')

def main():
    meta=get(BASE+'ogd-smn_meta_stations.csv');meta.raise_for_status()
    if not (ROOT/'metadata_source.csv').exists():(ROOT/'metadata_source.csv').write_bytes(meta.content)
    records={r['station_abbr']:r for r in csv.DictReader(io.StringIO(decode_source(meta.content)),delimiter=';') if 'Automatic weather stations' in r['station_type_en']}
    assert set(OLD)<=set(records)
    print('META',len(records),hashlib.sha256(meta.content).hexdigest(),flush=True)
    # Full 00/12 UTC catalog availability; HEAD only, never opens forecast fields.
    todo=[]
    for a,b in SEASONS:
        t=dt.datetime.fromisoformat(a);end=dt.datetime.fromisoformat(b)
        while t<end:
            for source in ('FOUR_v200_GFS','GRAP_v100_GFS','PANG_v100_GFS'):todo.append((source,t))
            t+=dt.timedelta(hours=12)
    av=ROOT/'archive_availability.jsonl';done=set()
    if av.exists():
        for line in av.read_text().splitlines():
            try:x=json.loads(line);done.add((x['source'],x['init_utc']))
            except Exception:pass
    def job(x):return archive_one(*x)
    with ThreadPoolExecutor(max_workers=12) as pool:
        fut={pool.submit(job,x):x for x in todo if (x[0],x[1].isoformat()+'Z') not in done}
        for i,f in enumerate(as_completed(fut),1):
            x=f.result()
            with av.open('a') as out:out.write(json.dumps(x)+'\n')
            if i%150==0:print('HEAD',i,len(fut),flush=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        fs=[pool.submit(fetch_station,r) for r in records.values()]
        stats=[f.result() for f in as_completed(fs)]
    (ROOT/'inventory_all.json').write_text(json.dumps(stats,indent=2,ensure_ascii=False))
    good=[]
    for s in stats:
        if 'counts' not in s:continue
        rates=[s['counts'][j].get(p,0)/s['expected'][j] for j in range(3) for p in ('fkl010z0','fkl010z1')]
        s['min_rate']=min(rates);s['eligible']=all(v>=.9 for v in rates)
        sid=s['station'];r=records[sid]
        terrain=OLD.get(sid,EXPOSURE.get(r['station_exposition_en']))
        s['terrain']=terrain
        if terrain and (s['eligible'] or sid in OLD):good.append(s)
    selected=[]
    for group in ('ridge','pass','valley','plateau','plain'):
        group_old=[s for s in good if s['station'] in OLD and OLD[s['station']]==group]
        group_new=sorted((s for s in good if s['station'] not in OLD and s['terrain']==group),key=lambda s:(-s['min_rate'],s['station']))
        selected+=sorted(group_old,key=lambda s:s['station'])+group_new[:max(0,8-len(group_old))]
    assert set(OLD)<=set(s['station'] for s in selected)
    freeze=dt.datetime.now(ZoneInfo('America/New_York')).isoformat()
    output=ROOT/'stations_p2_frozen.csv'
    with output.open('x',newline='') as f:
        fields=['station','lat','lon','elevation_m','terrain','station_exposition_en','selection','min_completeness_six','season_mean_rates','season_gust1_rates','wigos_id','wind_height_m','wind_height_deployment_begin','wind_height_source','obs_source_url','frozen_at_us_eastern']
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for s in selected:
            r=records[s['station']];den=s['expected'];cs=s['counts']
            w.writerow({'station':s['station'],'lat':r['station_coordinates_wgs84_lat'],'lon':r['station_coordinates_wgs84_lon'],'elevation_m':r['station_height_masl'],'terrain':s['terrain'],'station_exposition_en':s['exposure'],'selection':'v2_retained' if s['station'] in OLD else 'min_six_rates_desc','min_completeness_six':f"{s['min_rate']:.9f}",'season_mean_rates':';'.join(f"{cs[i].get('fkl010z0',0)/den[i]:.9f}" for i in range(3)),'season_gust1_rates':';'.join(f"{cs[i].get('fkl010z1',0)/den[i]:.9f}" for i in range(3)),'wigos_id':r['station_wigos_id'],'wind_height_m':'','wind_height_deployment_begin':'','wind_height_source':'','obs_source_url':s['url'],'frozen_at_us_eastern':freeze})
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    manifest={'freeze_time_eastern':freeze,'station_sha256':digest,'metadata_sha256':hashlib.sha256(meta.content).hexdigest(),'selected':len(selected),'counts':dict(Counter(s['terrain'] for s in selected)),'eligible':len([s for s in stats if s.get('eligible')]),'candidates':len(stats),'availability_checks':len(todo)}
    (ROOT/'freeze_manifest.json').write_text(json.dumps(manifest,indent=2))
    print('FROZEN',json.dumps(manifest),flush=True)
if __name__=='__main__':main()
