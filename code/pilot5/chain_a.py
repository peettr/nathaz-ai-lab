#!/usr/bin/env python3
"""Auditable pilot: HURDAT2 centers/intensity + ATCF b-deck RMW + IEM 1min ASOS.
No parameter is fitted to observations. This is a simplified Holland screening,
NOT the Vickery (2009) slab boundary-layer implementation.
"""
import argparse, csv, gzip, io, json, math, statistics, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from zoneinfo import ZoneInfo

OUT=Path(__file__).resolve().parent
HURDAT='https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2025-092326.txt'
ATCF='https://ftp.nhc.noaa.gov/atcf/archive/{year}/b{sid}.dat.gz'
GEO='https://mesonet.agron.iastate.edu/geojson/network/{state}_ASOS.geojson'
IEM='https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py'
CANDIDATES={'DELTA':('2020','202010092300', 'LA,TX'), 'ZETA':('2020','202010282100','LA,MS'),
 'IDA':('2021','202108291655','LA'), 'NICHOLAS':('2021','202109140530','TX'),
 'IAN':('2022','202209281905','FL'), 'NICOLE':('2022','202211100745','FL'),
 'IDALIA':('2023','202308301145','FL'), 'BERYL':('2024','202407080840','TX'),
 'DEBBY':('2024','202408051100','FL'), 'FRANCINE':('2024','202409112200','LA'),
 'HELENE':('2024','202409270310','FL'), 'MILTON':('2024','202410100030','FL')}
KNOT=.514444; EARTH=6371.; RHO=1.15

def fetch(url, timeout=50):
    with urlopen(Request(url, headers={'User-Agent':'ResearchLab/1.0 (public data research)'}),timeout=timeout) as r:return r.read()
def dt(s):return datetime.strptime(s,'%Y%m%d%H%M').replace(tzinfo=timezone.utc)
def coord(s):return float(s[:-1])*(1 if s[-1] in 'NE' else -1)
def atcf_coord(s):return int(s[:-1])/10*(1 if s[-1] in 'NE' else -1)
def km(a,b,c,d):
    p1,p2=math.radians(a),math.radians(c);x=math.sin((p2-p1)/2)**2+math.cos(p1)*math.cos(p2)*math.sin(math.radians(d-b)/2)**2
    return 2*EARTH*math.asin(min(1,math.sqrt(x)))
def parse_hurdat():
    lines=fetch(HURDAT).decode().splitlines();out={}
    for i,line in enumerate(lines):
        if not line.startswith('AL') or len(line)<28:continue
        h=[z.strip() for z in line.split(',')]
        if len(h)<3 or not h[2].isdigit():continue
        sid,name,n=h[0].lower(),h[1],int(h[2]);
        if name not in CANDIDATES or h[0][-4:]!=CANDIDATES[name][0]:continue
        rows=[]
        for raw in lines[i+1:i+1+n]:
            a=[z.strip() for z in raw.split(',')]
            try:rows.append({'t':dt(a[0]+a[1]),'record':a[2],'type':a[3],'lat':coord(a[4]),'lon':coord(a[5]),'v':float(a[6]),'p':float(a[7])})
            except (ValueError,IndexError):pass
        out[name]=(sid,rows)
    return out

def bdeck(sid):
    try: text=gzip.decompress(fetch(ATCF.format(year=sid[-4:],sid=sid))).decode()
    except Exception as ex:print('BDECK ERROR',sid,str(ex));return []
    out={}
    for raw in text.splitlines():
        a=[x.strip() for x in raw.split(',')]
        if len(a)<22 or a[4]!='BEST' or a[11]!='34':continue
        try:
            t=dt(a[2]+'00');rmw=float(a[19]);poci=float(a[17]);r=(rmw,poci)
            out[t]=r
        except (ValueError,IndexError):continue
    return sorted(out.items())

def interp(rows,t,keys):
    if not rows:return None
    lo=max((x for x in rows if x[0]<=t),default=None,key=lambda x:x[0]);hi=min((x for x in rows if x[0]>=t),default=None,key=lambda x:x[0]);
    if lo is None or hi is None:return None
    if (hi[0]-lo[0]).total_seconds()>7*3600:return None
    w=(t-lo[0]).total_seconds()/max(1,(hi[0]-lo[0]).total_seconds())
    return [x+(y-x)*w for x,y in zip(lo[1],hi[1])]

def stations(state,lat,lon,t):
    x=json.loads(fetch(GEO.format(state=state)))['features'];ans={}
    for f in x:
        p=f['properties'];slon,slat=f['geometry']['coordinates'][:2]
        if km(lat,lon,slat,slon)>150:continue
        start=p.get('archive_begin') or '1900-01-01';end=p.get('archive_end') or '2100-01-01'
        if not start[:10]<=t.date().isoformat()<=end[:10]:continue
        if p.get('attributes',{}).get('HAS1MIN')!='1':continue
        sid=p['sid'];ans[sid]={'station':sid,'name':p['sname'],'lat':slat,'lon':slon,'distance_km':km(lat,lon,slat,slon),'state':state,'tz':p.get('tzname') or 'America/New_York'}
    return ans

def obs(st,start,end):
    params={'station':st['station'],'vars':'sknt,gust_sknt','sts':start.strftime('%Y-%m-%dT%H:%MZ'),'ets':end.strftime('%Y-%m-%dT%H:%MZ'),'what':'download','tz':'UTC'}
    url=IEM+'?'+urlencode(params)
    try:
        raw=fetch(url,timeout=85).decode();rows=[]
        for a in csv.DictReader(io.StringIO(raw)):
            try: t=datetime.strptime(a['valid(UTC)'],'%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc)
            except (ValueError,KeyError):continue
            def val(k):
                try:return float(a[k])
                except (ValueError,KeyError):return None
            rows.append((t,val('sknt'),val('gust_sknt')))
        return rows,None,url
    except Exception as ex:return [],str(ex),url

def model(lat,lon,v_kt,p,r_m,st):
    # POCI from b-deck (not generic 1010); B from Vmax and pressure contrast.
    poci=r_m[1];rmw_nm=r_m[0];dp=(poci-p)*100
    if not 8<=rmw_nm<=200 or not 500<=dp<=15000:return None
    lat2,lon2=st['lat'],st['lon'];radius=max(3,km(lat,lon,lat2,lon2))*1000;rmw=rmw_nm*1852
    f=2*7.292115e-5*math.sin(math.radians(lat));vmax=v_kt*KNOT
    # gradient at RMW via surface reduction; pressure-derived B retains Coriolis.
    vg=vmax/.85;B=RHO*math.e*(vg*vg+vg*f*rmw)/dp
    if not .5<=B<=4:return None
    q=(rmw/radius)**B;g=max(0,math.sqrt(B*dp/RHO*q*math.exp(-q)+(radius*f/2)**2)-radius*f/2)
    # no extra local calibration; 0.85 is baseline documented by Vickery 2009.
    sustained=.85*g
    return sustained/KNOT,B

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--events',default='FRANCINE,HELENE,MILTON');ap.add_argument('--workers',type=int,default=3);args=ap.parse_args()
    h=parse_hurdat();events=[]; selected=args.events.upper().split(',');metadata={};allrows=[]
    for name,(year,time_s,states) in CANDIDATES.items():
        if name not in h:continue
        sid,track=h[name];t=dt(time_s);land=[x for x in track if x['t']==t and x['record']=='L'];
        if not land:print('MISSING LANDFALL',name);continue
        l=land[0];rmw=bdeck(sid);nearest=interp(rmw,t,('rmw','poci'))
        models={k:('yes' if (year!='2020' or t>=dt('202010010000')) and (k!='GRAP' or int(year)>=2022) else 'no') for k in ('PANG','FOUR','GRAP')}
        events.append({'name':name,'year':year,'atcf_id':sid.upper(),'landfall_local':t.astimezone(ZoneInfo('America/Chicago' if 'FL' not in states or l['lon']<-85 else 'America/New_York')).isoformat(),'landfall_utc':t.isoformat(),'lat':l['lat'],'lon':l['lon'],'vmax_kt':l['v'],'pmin_hpa':l['p'],'rmw_at_landfall_nm_interpolated':nearest[0] if nearest else '', 'bdeck_rmw_present':bool(nearest and nearest[0]>0),'PANG_24_48_72':models['PANG'],'FOUR_24_48_72':models['FOUR'],'GRAP_24_48_72':models['GRAP'],'model_coverage_note':'calendar-era candidate, exact objects and init/lead availability NOT checked','source':HURDAT+' ; '+ATCF.format(year=year,sid=sid)})
        metadata[name]=(sid,track,rmw,l,states)
    with (OUT/'events.csv').open('w',newline='') as f:w=csv.DictWriter(f,events[0].keys());w.writeheader();w.writerows(events)
    for name in selected:
        sid,track,rmw,l,states=metadata[name];t=l['t'];stations_all={}
        for state in states.split(','):stations_all.update(stations(state,l['lat'],l['lon'],t))
        print(name,'candidate_1min_stations',len(stations_all),flush=True)
        start,end=t-timedelta(hours=12),t+timedelta(hours=12)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            fs={pool.submit(obs,st,start,end):st for st in stations_all.values()}
            for fu in as_completed(fs):
                st=fs[fu];data,err,url=fu.result()
                # Retain stations with observed one-minute wind (regardless of survival); record dropouts explicitly.
                total=len(data);valid=[x for x in data if x[1] is not None];gust=[x for x in data if x[2] is not None]
                peak_s=max((x[1] for x in valid),default=None);peak_g=max((x[2] for x in gust),default=None)
                preds=[];bs=[]
                for k in range(0,24*4+1):
                    tm=start+timedelta(minutes=15*k)
                    a=interp([(x['t'],(x['lat'],x['lon'],x['v'],x['p'])) for x in track],tm,None);b=interp(rmw,tm,None)
                    if not a or not b:continue
                    res=model(*a,b,st)
                    if res:preds.append(res[0]);bs.append(res[1])
                pred=max(preds,default=None)
                allrows.append({'event':name,'atcf_id':sid.upper(),'station':st['station'],'station_name':st['name'],'state':st['state'],'lat':st['lat'],'lon':st['lon'],'distance_km':round(st['distance_km'],1),'obs_rows':total,'obs_sknt_rows':len(valid),'obs_gust_rows':len(gust),'expected_minutes':1440,'first_obs_utc':data[0][0].isoformat() if data else '', 'last_obs_utc':data[-1][0].isoformat() if data else '', 'obs_peak_sustained_kt':peak_s or '', 'obs_peak_5sec_gust_kt':peak_g or '', 'pred_peak_sustained_kt':round(pred,2) if pred is not None else '', 'ratio_sustained':round(pred/peak_s,4) if pred and peak_s else '', 'median_B':round(statistics.median(bs),3) if bs else '', 'fetch_error':err or '','source_url':url})
                print(name,st['station'],'obs',total,'gust',len(gust),'pred',round(pred or 0,1),flush=True)
    if allrows:
        with (OUT/'chain_a_station_rows.csv').open('w',newline='') as f:w=csv.DictWriter(f,allrows[0].keys());w.writeheader();w.writerows(sorted(allrows,key=lambda z:(z['event'],z['station'])))
        ratios=[float(x['ratio_sustained']) for x in allrows if x['ratio_sustained'] and x['obs_sknt_rows']>=720]
        summary={'selected':selected,'n_candidates':len(allrows),'n_valid_half_window':len(ratios),'median_abs_ratio_error':statistics.median(abs(x-1) for x in ratios) if ratios else None,'median_signed_ratio_bias':statistics.median(x-1 for x in ratios) if ratios else None,'event_counts':{e:sum(r['event']==e and bool(r['ratio_sustained']) and r['obs_sknt_rows']>=720 for r in allrows) for e in selected},'metric':'abs(pred/obs -1), signed(pred/obs -1); >=720 nonmissing sustained minutes in +/-12h','wind_metric':'sknt IEM 1min running 2-min mean; not yet equivalent to requested 1-min mean'}
        (OUT/'chain_a_summary.json').write_text(json.dumps(summary,indent=2));print('SUMMARY',json.dumps(summary))
if __name__=='__main__':main()
