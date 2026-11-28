#!/usr/bin/env python3
"""Uniform IEM scheduled-hour ASOS/METAR availability probe; no forecast–observation pairing."""
import csv, io, json, math, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
P=Path(__file__).resolve().parent; B=P.parent
UA={'User-Agent':'PETW research hourly metadata probe/1.0'}
def get(u,timeout=90):
    for attempt in range(2):
        try:return urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=timeout).read()
        except Exception:
            if attempt:raise
            time.sleep(2)
def dist(a,b,c,d):
    x=math.sin(math.radians(c-a)/2)**2+math.cos(math.radians(a))*math.cos(math.radians(c))*math.sin(math.radians(d-b)/2)**2
    return 12742*math.asin(min(1,math.sqrt(x)))
def fetch_group(event,sts,start,end):
    p=[('station',s) for s in sts]+[('data','sknt'),('year1',start.year),('month1',start.month),('day1',start.day),('hour1',start.hour),('minute1',start.minute),('year2',end.year),('month2',end.month),('day2',end.day),('hour2',end.hour),('minute2',end.minute),('tz','Etc/UTC'),('format','onlycomma'),('report_type','3'),('missing','M')]
    url='https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?'+urllib.parse.urlencode(p)
    out={s:set() for s in sts}
    try:
        for r in csv.DictReader(io.StringIO(get(url).decode())):
            s=r.get('station','').removeprefix('K')
            if s not in out:continue
            try:
                v=float(r['sknt']);t=datetime.strptime(r['valid'],'%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc)
                if v>=0 and start<=t<end:out[s].add(t.strftime('%Y-%m-%d %H'))
            except (ValueError,KeyError,TypeError):pass
        return out,''
    except Exception as e:return out,str(e)
def main():
    ev=[]
    for r in csv.DictReader((B/'events_verified.csv').open()):
        if r['name']=='NICHOLAS':continue
        ev.append(dict(event=r['name'],year=int(r['year']),atcf_id=r['atcf_id'],landfall_utc=r['landfall_utc'],lat=float(r['lat']),lon=float(r['lon']),vmax_kt=r['vmax_kt'],ofcl='yes_prior_s2b',pangu='yes_prior_s2b',source='NHC HURDAT2; events_verified.csv'))
    for r in csv.DictReader((B/'v2_new_events_probe.csv').open()):
        if r['event'] not in ('ETA','ELSA','FRED','HENRI'):continue
        ev.append(dict(event=r['event'],year=int(r['atcf_id'][-4:]),atcf_id=r['atcf_id'],landfall_utc=r['landfall_utc'],lat=float(r['lat']),lon=float(r['lon']),vmax_kt=r['wind_kt'],ofcl='yes_prior_probe',pangu='yes_prior_probe',source='NHC HURDAT2; v2_new_events_probe.csv'))
    # NHC public landfall update and contemporary operational b-deck, not yet in HURDAT2.
    ev.append(dict(event='ISAIAS',year=2026,atcf_id='AL092026',landfall_utc='2026-10-10T01:30:00+00:00',lat=30.4,lon=-86.5,vmax_kt=90,ofcl='to_check',pangu='to_check',source='https://www.nhc.noaa.gov/archive/2026/al09/al092026.update.10100129.shtml; location Destin approximate'))
    states=('AL','AR','CT','DE','FL','GA','LA','MA','MD','MS','NC','NJ','NY','PA','RI','SC','TX','VA')
    nets={st:json.loads(get(f'https://mesonet.agron.iastate.edu/geojson/network/{st}_ASOS.geojson'))['features'] for st in states}
    jobs=[];rows=[]
    for e in ev:
        t=datetime.fromisoformat(e['landfall_utc']);start=t-timedelta(hours=12);end=t+timedelta(hours=12)
        pool={}
        for st,features in nets.items():
            for f in features:
                p=f['properties'];id=p['sid'];lon,lat=f['geometry']['coordinates'][:2]
                d=dist(e['lat'],e['lon'],lat,lon)
                if d>150 or not (p.get('archive_begin') or '1900')[:10]<=t.date().isoformat()<=(p.get('archive_end') or '2100')[:10]:continue
                # IEM ASOS network contains ASOS, AWOS and other METAR sites; subtype requires independent verification.
                pool[id]={'event':e['event'],'year':e['year'],'atcf_id':e['atcf_id'],'landfall_utc':e['landfall_utc'],'latitude':e['lat'],'longitude':e['lon'],'vmax_kt':e['vmax_kt'],'station':id,'network':p.get('network',st+'_ASOS'),'station_type':'ASOS/AWOS subtype unverified','distance_km':round(d,2),'station_elevation_m':p.get('elevation',''),'elevation_metadata':bool(p.get('elevation') is not None),'anemometer_height_m':'','anemometer_height_metadata':False,'window':'landfall UTC +/-12h proxy; scheduled hourly METAR','start_utc':start.isoformat(),'end_utc':end.isoformat(),'valid_hour_bins':0,'coverage_fraction':0,'hourly_75pct':False,'fetch_error':'','ofcl_48':e['ofcl'],'pangu_48':e['pangu'],'landfall_source':e['source']}
        rows.extend(pool.values())
        ids=sorted(pool)
        for i in range(0,len(ids),18):jobs.append((e['event'],ids[i:i+18],start,end))
    observed={};errors={}
    with ThreadPoolExecutor(max_workers=6) as ex:
        fs={ex.submit(fetch_group,*j):j for j in jobs}
        for f in as_completed(fs):
            j=fs[f];v,err=f.result();observed.update({(j[0],k):a for k,a in v.items()});errors.update({(j[0],k):err for k in v})
    for r in rows:
        k=(r['event'],r['station']);r['valid_hour_bins']=len(observed.get(k,set()));r['coverage_fraction']=round(r['valid_hour_bins']/24,4);r['hourly_75pct']=r['valid_hour_bins']>=18;r['fetch_error']=errors.get(k,'')
    with (P/'hourly_pool_150km.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,rows[0].keys());w.writeheader();w.writerows(rows)
    print('requests',len(jobs),'station rows',len(rows),'errors',sum(bool(r['fetch_error']) for r in rows))
    for e in ev:
        rr=[r for r in rows if r['event']==e['event']];print(e['event'],len(rr),sum(r['hourly_75pct'] for r in rr))
if __name__=='__main__':main()
