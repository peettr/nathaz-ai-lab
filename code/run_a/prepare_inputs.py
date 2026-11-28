#!/usr/bin/env python3
"""Stage public BEST, IEM scheduled METAR, and frozen station identities on Colab CPU.
No model/observation pairing; never modifies frozen preregistration or station table.
"""
import csv,gzip,hashlib,io,json,urllib.request,urllib.parse,time,collections
from datetime import datetime,timedelta,timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
P=Path('/content/a_inputs_v2'); P.mkdir(exist_ok=True)
UA={'User-Agent':'PETW R23.3a BEST chain(a) public archive staging'}
def fetch(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=90) as f:return f.read()
def csvout(name,rows,fields):
    with (P/name).open('x',newline='') as f:
        w=csv.DictWriter(f,fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
def when(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
def parsecoord(s):return int(s[:-1])/10*(1 if s[-1] in 'NE' else -1)
def main():
    frozen=list(csv.DictReader(open('/content/homr_audit_frozen.csv')))
    pool={(r['event'],r['station']):r for r in csv.DictReader(open('/content/hourly_pool_150km.csv'))}
    chosen=[r for r in frozen if r['primary_eligible']=='yes_unverified_height']
    assert len({r['event'] for r in chosen})==15
    stations=[]; landfalls=[]; catalog=[]; tracks=[]; jobs=[]
    for ev in sorted({r['event'] for r in chosen}):
        rs=[r for r in chosen if r['event']==ev]
        relevant=[r for r in frozen if r['event']==ev]
        ident={pool[(ev,r['station'])]['atcf_id'] for r in rs}
        assert len(ident)==1,(ev,ident)
        atcf=ident.pop().lower();year=atcf[-4:];sid=atcf
        t=when(rs[0]['landfall_utc']); landfalls.append({'event':ev,'landfall_utc':t.isoformat()})
        for r in rs:
            q=pool[(ev,r['station'])]
            assert q['hourly_75pct']=='True',(ev,r['station'])
            stations.append(dict(r,lat=q['latitude'] if 'station_latitude' not in q else q['station_latitude'],lon=q['longitude']))
        # IEM pool latitude/longitude are storm-center, NOT station coordinates.
        url=f'https://ftp.nhc.noaa.gov/atcf/archive/{year}/b{sid}.dat.gz'
        try:
            blob=fetch(url); text=gzip.decompress(blob).decode()
            catalog.append({'event':ev,'url':url,'sha256':hashlib.sha256(blob).hexdigest(),'bytes':len(blob),'status':'ok'})
            window=[]; bytime={}
            for line in text.splitlines():
                a=[v.strip() for v in line.split(',')]
                if len(a)<24 or a[4]!='BEST' or a[11] not in ('34','50','64'):continue
                try:
                    tm=datetime.strptime(a[2],'%Y%m%d%H').replace(tzinfo=timezone.utc)
                    if not t-timedelta(hours=19)<=tm<=t+timedelta(hours=19):continue
                    key=tm.isoformat(); k=a[11];quad=tuple(float(a[j]) for j in (13,14,15,16))
                    v=dict(time_utc=key,lat=parsecoord(a[6]),lon=parsecoord(a[7]),vmax_kt=float(a[8]),pc_hpa=float(a[9]),penv_hpa=float(a[17]))
                    bytime.setdefault(key,{}).setdefault('base',v)
                    bytime[key].setdefault(k,quad)
                except (ValueError,IndexError):continue
            for key,info in sorted(bytime.items()):
                # pressure and position must be present on same BEST node; no cross-source filling.
                if not 'base' in info:continue
                line=dict(event=ev,**info['base'])
                for k in (34,50,64):
                    for q,value in zip(('ne','se','sw','nw'),info.get(str(k),(0,0,0,0))):line[f'r{k}_{q}_nmi']=value
                tracks.append(line)
            print('BEST',ev,'nodes',len(bytime),'thresholds',collections.Counter(k for v in bytime.values() for k in (34,50,64) if str(k) in v),flush=True)
        except Exception as e:
            catalog.append({'event':ev,'url':url,'sha256':'','bytes':0,'status':repr(e)});print('BEST ERROR',ev,repr(e),flush=True)
        ids=sorted({r['station'] for r in relevant if r['primary_eligible']=='yes_unverified_height'})
        start=(t-timedelta(hours=15)).replace(minute=0,second=0)
        end=(t+timedelta(hours=16)).replace(minute=0,second=0)
        for i in range(0,len(ids),15):jobs.append((ev,ids[i:i+15],start,end))
    # Pull station coordinates from IEM geojson (the pool's latitude/longitude are storm center!).
    states=('AL','AR','CT','DE','FL','GA','LA','MA','MD','MS','NC','NJ','NY','PA','RI','SC','TX','VA')
    geodata={}
    for state in states:
        try:
            data=json.loads(fetch(f'https://mesonet.agron.iastate.edu/geojson/network/{state}_ASOS.geojson'))
            for feature in data['features']:
                latlon=feature['geometry']['coordinates'][:2]
                geodata.setdefault(feature['properties']['sid'],[]).append((latlon[1],latlon[0],state))
        except Exception as e:print('GEO ERROR',state,repr(e),flush=True)
    missing=[]
    for row in stations:
        coords=geodata.get(row['station'],[])
        if not coords:missing.append((row['event'],row['station'])); row['lat']=row['lon']=''
        else:
            # Choose closest within 150km to event center; do not silently accept duplicate ID.
            q=pool[(row['event'],row['station'])]
            import math
            def dist(c):
                a,b=map(math.radians,(float(q['latitude']),c[0]));dl=math.radians(float(q['longitude'])-c[1]);h=math.sin((a-b)/2)**2+math.cos(a)*math.cos(b)*math.sin(dl/2)**2
                return 12742*math.asin(min(1,math.sqrt(h)))
            coords=sorted(coords,key=dist)
            if dist(coords[0])>151:missing.append((row['event'],row['station'],'distance>151km'))
            row['lat'],row['lon']=coords[0][:2]
    print('GEO missing/mismatch',missing,flush=True)
    observations=[];errors=[];urls=[]
    def job(j):
        ev,ids,start,end=j
        params=[('station',s) for s in ids]+[('data','sknt'),('data','gust_sknt'),('year1',start.year),('month1',start.month),('day1',start.day),('hour1',start.hour),('minute1',start.minute),('year2',end.year),('month2',end.month),('day2',end.day),('hour2',end.hour),('minute2',end.minute),('tz','Etc/UTC'),('format','onlycomma'),('report_type','3'),('missing','M')]
        url='https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?'+urllib.parse.urlencode(params)
        text=fetch(url).decode();r=list(csv.DictReader(io.StringIO(text)))
        return ev,ids,url,r
    with ThreadPoolExecutor(max_workers=4) as ex:
        future={ex.submit(job,j):j for j in jobs}
        for fut in as_completed(future):
            j=future[fut]
            try:
                ev,ids,url,rows=fut.result(); urls.append({'event':ev,'stations':','.join(ids),'url':url,'rows':len(rows)})
                for r in rows:
                    station=r.get('station','').removeprefix('K')
                    if station not in ids:continue
                    try:tm=datetime.strptime(r['valid'],'%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc).isoformat()
                    except (ValueError,KeyError):continue
                    observations.append({'event':ev,'station':station,'time_utc':tm,'sknt':r.get('sknt',''),'gust_sknt':r.get('gust_sknt',''),'report_type':'3'})
                print('IEM',ev,len(ids),len(rows),flush=True)
            except Exception as e:errors.append({'event':j[0],'stations':','.join(j[1]),'error':repr(e)});print('IEM ERROR',j[0],repr(e),flush=True)
    fields=list(tracks[0]) if tracks else ['event','time_utc','lat','lon','vmax_kt','pc_hpa','penv_hpa']
    csvout('tracks.csv',tracks,fields);csvout('stations.csv',stations,list(stations[0]));csvout('observations.csv',observations,['event','station','time_utc','sknt','gust_sknt','report_type']);csvout('landfalls.csv',landfalls,['event','landfall_utc'])
    (P/'manifest.json').write_text(json.dumps({'best':catalog,'iem':urls,'errors':errors,'geo_missing':missing,'counts':{'tracks':len(tracks),'stations':len(stations),'observations':len(observations)},'sha256':{x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in P.glob('*.csv')}},indent=2))
    print('STAGE FINISH',len(tracks),len(stations),len(observations),len(errors),flush=True)
if __name__=='__main__': main()
