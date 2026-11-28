#!/usr/bin/env python3
"""DAT 2019–2024 census with nearest IEM gust candidates; immutable r2 source files."""
import csv, datetime as D, json, math, pathlib, re, sys, time, urllib.parse
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
P=pathlib.Path(__file__).parent
DAT='https://services.dat.noaa.gov/arcgis/rest/services/nws_damageassessmenttoolkit/DamageViewer/FeatureServer/0/query'
IEM='https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py'
ST='https://mesonet.agron.iastate.edu/geojson/network/{}_ASOS.geojson'
UA={'User-Agent':'NotreDame-research-DAT-IEM-pairing/1.0'}
def get(url,params=None,raw=False):
    for i in range(3):
        try:
            r=requests.get(url,params=params,headers=UA,timeout=150);r.raise_for_status()
            if raw:return r.text
            v=r.json()
            if 'error' in v:raise ValueError(v['error'])
            return v
        except Exception:
            if i==2:raise
            time.sleep(3*(i+1))
def km(a,b,c,d):
    p1,p2=math.radians(a),math.radians(c);dp=p2-p1;dl=math.radians(d-b)
    return 12742*math.asin(min(1,math.sqrt(math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2)))
def stamp(ms):return D.datetime.fromtimestamp(ms/1000,D.timezone.utc)
def dump(name,data):
    path=P/name
    if path.exists():raise FileExistsError(path)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def dat_census():
    rows=[];counts=[]
    for year in range(2019,2025):
      for ef in ('TSTM/Wind','Tropical'):
        where=f"stormdate >= TIMESTAMP '{year}-01-01 00:00:00' AND stormdate < TIMESTAMP '{year+1}-01-01 00:00:00' AND efscale = '{ef}'"
        base={'f':'json','where':where};n=get(DAT,{**base,'returnCountOnly':'true'})['count'];pages=[]
        for off in range(0,n,1000):
            q={**base,'outFields':'objectid,stormdate,windspeed,damage_txt,efscale,event_id,lat,lon,comments','returnGeometry':'false','orderByFields':'objectid','resultOffset':off,'resultRecordCount':1000}
            v=get(DAT,q);pages+= [f['attributes'] for f in v['features']]
        if len(pages)!=n or len({x['objectid'] for x in pages})!=n:raise RuntimeError(f'DAT count mismatch {year} {ef}')
        rows+=pages;counts.append({'year':year,'efscale':ef,'count':n,'page_size':1000});print('DAT',year,ef,n,flush=True)
    dump('dat_census_2019_2024_r2.json',{'source':DAT,'queries':counts,'features':rows})

def station_census():
    states='AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY PR'.split()
    def one(st):
        v=get(ST.format(st));out=[]
        for f in v.get('features',[]):
            p=f['properties'];coordinates=f.get('geometry',{}).get('coordinates')
            if not coordinates:continue
            out.append({'id':f['id'],'state':st,'lat':coordinates[1],'lon':coordinates[0],'begin':p.get('archive_begin'),'end':p.get('archive_end')})
        return st,out
    allrows=[]
    with ThreadPoolExecutor(max_workers=8) as ex:
        for fut in as_completed([ex.submit(one,s) for s in states]):
            st,rr=fut.result();allrows+=rr;print('stations',st,len(rr),flush=True)
    dump('iem_station_census_r2.json',{'source':ST,'stations':allrows})

def plan():
    points=json.loads((P/'dat_census_2019_2024_r2.json').read_text())['features'];stations=json.loads((P/'iem_station_census_r2.json').read_text())['stations']
    # Longitudes outside CONUS/AK/HI can be valid; geographic coarse grid only accelerates distance test.
    grid=defaultdict(list)
    for s in stations:grid[(int(math.floor(s['lat'])),int(math.floor(s['lon'])))].append(s)
    jobs=defaultdict(set);relations=[];missing=Counter()
    for p in points:
        lat,lon,ms=p.get('lat'),p.get('lon'),p.get('stormdate')
        if lat is None or lon is None or ms is None:missing['missing_coordinates_or_time']+=1;continue
        t=stamp(ms);key=(p['objectid'],t.year, p['efscale'])
        near=[]
        for yy in range(math.floor(lat)-1,math.floor(lat)+2):
          for xx in range(math.floor(lon)-1,math.floor(lon)+2):
            for s in grid.get((yy,xx),[]):
                if s['begin'] and s['begin']>t.date().isoformat():continue
                if s['end'] and s['end']<t.date().isoformat():continue
                dis=km(lat,lon,s['lat'],s['lon'])
                if dis<=25:near.append((dis,s))
        if not near:missing['no_station_within_25km']+=1;continue
        for dis,s in near:
            # Query daily for point time +/- 12/3h, with single-day padding to guard UTC midnight.
            win=D.timedelta(hours=12 if p['efscale']=='Tropical' else 3)
            day=(t-win).date()
            while day<=(t+win).date():jobs[(s['state'],day.strftime('%Y-%m'))].add(s['id']);day+=D.timedelta(days=1)
        relations.append({'objectid':p['objectid'],'year':t.year,'efscale':p['efscale'],'dat_utc':t.isoformat(),'lat':lat,'lon':lon,'windspeed':p.get('windspeed'),'near':[(s['state'],s['id'],round(dis,6)) for dis,s in sorted(near,key=lambda z:z[0])],'midnight':t.hour==0 and t.minute==0})
    dump('pair_plan_r2.json',{'relations':relations,'jobs':[{'state':state,'month':month,'stations':sorted(ids)} for (state,month),ids in sorted(jobs.items())],'missing':missing,'point_count':len(points)})
    print('plan',len(relations),'jobs',len(jobs),'station-month',sum(len(v) for v in jobs.values()),'missing',missing,flush=True)

def observations():
    plan=json.loads((P/'pair_plan_r2.json').read_text());jobs=plan['jobs'];dest=P/'iem_month_cache_r2';dest.mkdir(exist_ok=True)
    tasks=[]
    for job in jobs:
        state,month=job['state'],job['month'];yy,mm=map(int,month.split('-'))
        end=(D.date(yy+1,1,1) if mm==12 else D.date(yy,mm+1,1))
        for j in range(0,len(job['stations']),15):
            ss=job['stations'][j:j+15];tag=f'{state}_{month}_{j//15:02d}';target=dest/(tag+'.csv')
            if target.exists():continue
            q={'station':ss,'data':'gust','year1':yy,'month1':mm,'day1':1,'year2':end.year,'month2':end.month,'day2':end.day,'tz':'Etc/UTC','format':'onlycomma','latlon':'yes','missing':'M','report_type':[3,4]}
            tasks.append((tag,q,target))
    print('IEM outstanding requests',len(tasks),flush=True)
    def one(task):
        tag,q,target=task;raw=get(IEM,q,raw=True)
        lines=raw.splitlines()
        if not lines or 'gust' not in lines[0].split(','):raise ValueError('IEM malformed '+tag+' '+raw[:120])
        # Store only gust rows; atomic write avoids treating incomplete downloads as valid.
        parsed=[r for r in csv.DictReader(lines) if r.get('gust') not in ('M','',None,'None')]
        tmp=target.with_suffix('.partial');tmp.write_text('station,valid,lon,lat,gust\n'+''.join(','.join(r.get(k,'') for k in ('station','valid','lon','lat','gust'))+'\n' for r in parsed));tmp.rename(target)
        return tag,len(parsed)
    done=0
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures=[ex.submit(one,t) for t in tasks]
        for fut in as_completed(futures):
            tag,n=fut.result();done+=1
            if done%25==0 or done==len(tasks):print('IEM',done,'/',len(tasks),'last',tag,n,flush=True)

def analyze():
    plan=json.loads((P/'pair_plan_r2.json').read_text());dest=P/'iem_month_cache_r2';obs=defaultdict(list)
    for path in dest.glob('*.csv'):
        with path.open() as f:
            for r in csv.DictReader(f):
                try:obs[(path.name.split('_')[0],r['station'])].append((D.datetime.fromisoformat(r['valid']).replace(tzinfo=D.timezone.utc),float(r['gust'])))
                except (ValueError,KeyError):pass
    # Same station ID across states remains disambiguated by network.
    for v in obs.values():v.sort()
    out=[];dist=Counter();groups=defaultdict(set);diffs=defaultdict(list);anom=[]
    for rel in plan['relations']:
        t=D.datetime.fromisoformat(rel['dat_utc']);window=D.timedelta(hours=12 if rel['efscale']=='Tropical' else 3);chosen=None
        for state,station,d in rel['near']:
            valid=[(ot,g) for ot,g in obs.get((state,station),[]) if abs(ot-t)<=window]
            if not valid:continue
            ot,g=min(valid,key=lambda x:(abs(x[0]-t),x[0]));peak_time,peak=max(valid,key=lambda x:(x[1],-abs((x[0]-t).total_seconds())))
            chosen=(state,station,d,ot,g,peak_time,peak)
            break
        if not chosen:continue
        state,station,d,ot,g,peak_time,peak=chosen;year=rel['year'];ef=rel['efscale'];key=(year,ef)
        value=rel['windspeed'];m=re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*',str(value or ''));dat_mph=float(m.group(1)) if m and float(m.group(1))>0 else None
        rec={k:rel[k] for k in ('objectid','year','efscale','dat_utc','lat','lon','windspeed','midnight')}
        rec.update(station=station,network=state+'_ASOS',distance_km=d,nearest_gust_kt=g,nearest_utc=ot.isoformat(),max_gust_kt=peak,max_utc=peak_time.isoformat(),max_minus_nearest_kt=peak-g,dat_windspeed_mph=dat_mph,nearest_mph=g*1.150779448,max_mph=peak*1.150779448,dat_minus_nearest_mph=(dat_mph-g*1.150779448 if dat_mph is not None else None),dat_minus_max_mph=(dat_mph-peak*1.150779448 if dat_mph is not None else None),gust_over_100kt=(g>100 or peak>100))
        out.append(rec)
        if rec['gust_over_100kt']:anom.append(rec['objectid'])
        for threshold in (10,25):
            if d<=threshold:
                dist[(year,ef,threshold)]+=1
                # Station-time group = exact station + selected nearest METAR valid time, not independent damage point.
                groups[(year,ef,threshold)].add((state,station,ot.isoformat()))
                if dat_mph is not None:diffs[(year,ef,threshold)].append(rec['dat_minus_max_mph'])
    if len(out)!=len({r['objectid'] for r in out}):raise RuntimeError('duplicate DAT objectid')
    import statistics
    def quantile(values,q):
        if not values:return None
        s=sorted(values);i=(len(s)-1)*q;lo=int(i);return s[lo]+(s[min(lo+1,len(s)-1)]-s[lo])*(i-lo)
    table=[]
    for year in range(2019,2025):
      for ef in ('TSTM/Wind','Tropical'):
       for threshold in (10,25):
        vals=diffs[(year,ef,threshold)];table.append({'year':year,'efscale':ef,'km':threshold,'matched_points':dist[(year,ef,threshold)],'station_time_groups':len(groups[(year,ef,threshold)]),'dat_windspeed_numeric_pairs':len(vals),'dat_minus_max_mph_p10':quantile(vals,.1),'median':quantile(vals,.5),'p90':quantile(vals,.9)})
    dump('pair_scale_stats_r2.json',{'definition':'nearest spatial station with gust +/-3h TSTM/Wind, +/-12h Tropical; exact station+nearest METAR timestamp grouping, DAT mph numeric assumed, negative/sentinel invalid; max and nearest both reported','table':table,'matched_total':len(out),'anomaly_point_ids':anom,'observations_with_gust_station_months':len(obs),'missing':plan['missing']})
    name=P/'dat_iem_pairs_scale_r2.csv'
    if name.exists():raise FileExistsError(name)
    with name.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
    print('analysis finished',len(out),'anomaly',len(anom),flush=True)

if __name__=='__main__':
    steps={'dat':dat_census,'stations':station_census,'plan':plan,'iem':observations,'analyze':analyze}
    for arg in sys.argv[1:]:steps[arg]()
