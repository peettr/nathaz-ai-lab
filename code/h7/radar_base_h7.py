#!/usr/bin/env python3
"""Two Dallas H4 windows: KFWS lowest velocity sweep |Vr| feasibility, no 10-m conversion.
Reads public Unidata mirror of NOAA NEXRAD Level II and H4 local read-only files.
All newly generated files reside beside this script. Does not cache radar binaries.
"""
import csv, io, json, math, re, sys, time, warnings, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests
import numpy as np
from scipy.ndimage import median_filter
import pyart
P=Path(__file__).resolve().parent
H4=P.parent/'h4'
BASE='https://unidata-nexrad-level2.s3.amazonaws.com/'
NS={'s':'http://s3.amazonaws.com/doc/2006-03-01/'}
DAYS=['20240601','20250709']
radar_requests=[]

def list_day(dt):
    prefix=dt.strftime('%Y/%m/%d')+'/KFWS/'
    resp=requests.get(BASE,params={'list-type':'2','prefix':prefix,'max-keys':1000},timeout=30)
    resp.raise_for_status();root=ET.fromstring(resp.content)
    assert root.find('s:IsTruncated',NS).text=='false',prefix
    for c in root.findall('s:Contents',NS):
        key=c.find('s:Key',NS).text
        m=re.search(r'KFWS(\d{8}_\d{6})_V\d\d$',key)
        if m:yield datetime.strptime(m.group(1),'%Y%m%d_%H%M%S').replace(tzinfo=timezone.utc),key,int(c.find('s:Size',NS).text)

def station_rows():
    with (H4/'stations_h4.csv').open() as f:
        stations={r['station']:r for r in csv.DictReader(f)}
    with (H4/'station_clean_h4.csv').open() as f:
        print('clean headers',next(csv.reader(f)))
    with (H4/'peaks_h4v3.csv').open() as f:
        peaks={(r['event'].replace('-',''),r['station']):r for r in csv.DictReader(f) if r['event'].replace('-','') in DAYS}
    return stations,peaks

def sample(r,s,corrected,stations):
    sl=r.get_slice(s)
    az=r.azimuth['data'][sl]
    rg=r.range['data']/1000
    v=np.ma.filled(corrected['data'][sl],np.nan)
    raw=np.ma.filled(r.get_field(s,'velocity'),np.nan)
    sw=np.ma.filled(r.get_field(s,'spectrum_width'),np.inf)
    # The nearest reflectivity sweep has matching resolution in Level II, but
    # availability is checked rather than extrapolating reflectivity to gust.
    sr=min(range(r.nsweeps),key=lambda i:abs(float(r.fixed_angle['data'][i])-float(r.fixed_angle['data'][s])) if np.ma.count(r.get_field(i,'reflectivity')) else 999)
    z=np.ma.filled(r.get_field(sr,'reflectivity'),np.nan)
    zaz=r.azimuth['data'][r.get_slice(sr)]
    zrg=r.range['data']/1000
    lat0=float(r.latitude['data'][0]);lon0=float(r.longitude['data'][0]); alt0=float(r.altitude['data'][0])
    out={}
    for name,st in stations.items():
        lat=float(st['lat']);lon=float(st['lon']);elev=float(st['elevation'])
        x=(lon-lon0)*111.195*math.cos(math.radians((lat+lat0)/2));y=(lat-lat0)*111.195
        dist=math.hypot(x,y);bearing=(math.degrees(math.atan2(x,y))+360)%360
        a=int(np.argmin(abs((az-bearing+180)%360-180)));k=int(np.argmin(abs(rg-dist)))
        ka=np.array([i for i in (a-1,a,a+1) if 0<=i<len(az)])
        kk=np.array([i for i in (k-1,k,k+1) if 0<=i<len(rg)])
        zz_a=int(np.argmin(abs((zaz-bearing+180)%360-180)));zz_k=int(np.argmin(abs(zrg-dist)))
        refl=float(z[zz_a,zz_k]) if zz_k<z.shape[1] else float('nan')
        block=v[np.ix_(ka,kk)];width=sw[np.ix_(ka,kk)];rawblock=raw[np.ix_(ka,kk)]
        ok=np.isfinite(block)&np.isfinite(rawblock)&(width<=8)
        values=block[ok]
        # Nearest 3x3 coherent patch; reject isolated wraps and absent echo.
        if len(values)<4 or not np.isfinite(refl) or refl<10 or float(np.median(np.abs(values-np.median(values))))>5:
            continue
        est=float(np.median(np.abs(values)))
        theta=math.radians(float(r.fixed_angle['data'][s]));rm=dist*1000
        height=alt0+rm*math.sin(theta)+rm*rm/(2*(4/3)*6371000)-elev
        out[name]={'radial_abs_ms':est,'beam_center_agl_m':height,'radar_range_km':dist,'elevation_deg':math.degrees(theta),'reflectivity_dbz':refl,'valid_neighbour_gates':len(values)}
    return out

def run():
    stations,peaks=station_rows()
    prior=P/'radar_scan_audit_h6.json'; old=json.loads(prior.read_text()) if prior.exists() else {}
    scanned=P/'radar_station_scans_h6.csv'
    if scanned.exists():
        with scanned.open() as f:allrows=list(csv.DictReader(f))
    else:allrows=[]
    audit={}
    for day in DAYS:
        w=json.loads((H4/f'window_{day}_h4.json').read_text());start=datetime.fromisoformat(w['window_start']);end=datetime.fromisoformat(w['window_end'])
        # Include preceding scan by 5 min; end + one scan, times checked below.
        keys=sorted((t,k,n) for d in {start.date(),end.date()} for t,k,n in list_day(datetime.combine(d,datetime.min.time(),timezone.utc)) if start-timedelta(minutes=5)<=t<=end)
        assert keys,day
        audit[day]=old.get(day) or {'window_start_utc':w['window_start'],'window_end_utc':w['window_end'],'volumes_listed':len(keys),'compressed_bytes':sum(n for _,_,n in keys),'processed':0,'failed':[],'radar':'KFWS','source':BASE}
        print(day,len(keys),'MB',round(sum(n for _,_,n in keys)/1e6,1),'resume',audit[day]['processed'],flush=True)
        for j,(t,key,n) in enumerate(keys):
            if j<audit[day]['processed']:continue
            try:
                resp=requests.get(BASE+key,timeout=90);resp.raise_for_status()
                assert len(resp.content)==n,(key,len(resp.content),n)
                r=pyart.io.read_nexrad_archive(io.BytesIO(resp.content));del resp
                sweeps=[i for i in range(r.nsweeps) if np.ma.count(r.get_field(i,'velocity'))>1000]
                s=min(sweeps,key=lambda i:float(r.fixed_angle['data'][i]))
                ny=float(r.get_nyquist_vel(s,check_uniform=False))
                if not 0<ny<100:raise ValueError('invalid nyquist '+str(ny))
                gf=pyart.filters.GateFilter(r);gf.exclude_masked('velocity')
                corrected=pyart.correct.dealias_region_based(r,gatefilter=gf,vel_field='velocity',check_nyquist_uniform=False)
                found=sample(r,s,corrected,stations)
                for name,one in found.items():
                    if (day,name) in peaks:
                        allrows.append({'event':day,'station':name,'scan_utc':t.isoformat(),'volume':key.rsplit('/',1)[-1],'nyquist_ms':ny,**one})
                audit[day]['processed']+=1
                del r,corrected
            except Exception as exc:
                audit[day]['failed'].append({'volume':key,'error':repr(exc)[:250]})
            if (j+1)%10==0:
                print(day,j+1,len(keys),'valid station-scans',len(allrows),flush=True)
                save(allrows,audit)
        save(allrows,audit)
    print('DONE',len(allrows),{d:(a['processed'],len(a['failed'])) for d,a in audit.items()})

def save(rows,audit):
    (P/'radar_scan_audit_h6.json').write_text(json.dumps(audit,indent=2)+'\n')
    path=P/'radar_station_scans_h6.csv'
    with path.open('w',newline='') as f:
        if rows:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        else:f.write('event,station,scan_utc,radial_abs_ms\n')
if __name__=='__main__':run()
