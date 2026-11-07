"""Validate distinct Storm Events candidates with IEM METAR PK WND; candidate controls only."""
import csv, datetime as dt, io, pathlib, re, sys, time, urllib.parse, urllib.request, math
from collections import Counter
ROOT=pathlib.Path(__file__).parent
candidates=list(csv.DictReader((ROOT/'candidate_catalog.csv').open(newline='')))

def distance(a,b,c,d):
    a,c=math.radians(a),math.radians(c); dl=math.radians(d-b)
    x=math.sin((c-a)/2)**2+math.cos(a)*math.cos(c)*math.sin(dl/2)**2
    return 12742*math.asin(min(1,math.sqrt(x)))

def fetch(station,start,end):
    params={'station':station,'sts':start.strftime('%Y-%m-%dT%H:%MZ'),'ets':end.strftime('%Y-%m-%dT%H:%MZ'),'tz':'UTC','data':'gust,peak_wind_gust,peak_wind_time,metar','format':'onlycomma','missing':'M','report_type':'3,4'}
    url='https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?'+urllib.parse.urlencode(params)
    with urllib.request.urlopen(url,timeout=45) as f: body=f.read().decode('utf-8-sig')
    return list(csv.DictReader(io.StringIO(body))),url

def peak(records,target):
    vals=[]
    for x in records:
        try:
            speed=max(float(x[k]) for k in ('gust','peak_wind_gust') if x.get(k) not in ('','M',None))
            stamp=x.get('peak_wind_time') if x.get('peak_wind_gust') not in ('','M',None) else x['valid']
            when=dt.datetime.strptime(stamp,'%Y-%m-%d %H:%M')
            if abs((when-target).total_seconds())<=3600: vals.append((speed,when,x))
        except (ValueError,KeyError):pass
    return max(vals,key=lambda z:z[0]) if vals else None

selected=[]; checked=0; used=set(); per_station=Counter();
# Cold-month and summer coverage; unique days and stations, order reproducible.
for r in sorted(candidates,key=lambda x:(int(x['year']), x['peak_candidate_utc'])):
    year=int(r['year']);
    if year not in (2023,2024,2025,2026): continue
    if year==2025 and r['peak_candidate_utc'][:10]>'2025-09-30':continue
    if len([s for s in selected if s['group']=='v1'])>=23 and len([s for s in selected if s['group']=='conus'])>=12:break
    group='conus' if year==2026 else 'v1'
    limit=12 if group=='conus' else 23
    if len([s for s in selected if s['group']==group])>=limit:continue
    day=r['peak_candidate_utc'][:10]
    if (group,day) in used or per_station[(group,r['station'])]>=4:continue
    candidate=dt.datetime.fromisoformat(r['peak_candidate_utc'].replace('Z',''))
    try:
        records,url=fetch(r['station'],candidate-dt.timedelta(hours=1),candidate+dt.timedelta(hours=2))
        p=peak(records,candidate);checked+=1
        if not p or p[0]<50:continue
        kt,when,report=p
        if abs(kt-float(r['gust_kt']))>3:continue
        selected.append(dict(group=group,id=r['id'],station=r['station'],utc=when.isoformat(),obs_kt=kt,lat=r['lat'],lon=r['lon'],state=r['state'],year=year,ncei_url=r['url'],iem_url=url,metar=report.get('metar',''),qc='PK_WND_OR_METAR_MATCH;NOT_RAW_SENSOR',selection='distinct_UTC_day_station_cap4'))
        used.add((group,day));per_station[(group,r['station'])]+=1
        print('VERIFIED',group,r['id'],r['station'],when,kt,flush=True)
    except Exception as ex:print('FETCH_ERROR',r['id'],repr(ex),flush=True)
fields=list(selected[0]) if selected else []
if fields:
    with (ROOT/'events_r2_verified.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(selected)
print('SUMMARY',dict(Counter(x['group'] for x in selected)),'IEM_QUERIES',checked,flush=True)
