#!/usr/bin/env python3
"""R23.3a-05 paired hourly-vs-minute observation sampling; Colab CPU only."""
import csv, io, json, math, statistics, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

P=Path('/content'); UTC=timezone.utc
SRC=P/'a_v3_r2_main.csv'; LAN=P/'landfalls.csv'
OUT=P/'sampling_rows.csv'; LOG=P/'requests.csv'; SUMMARY=P/'sampling_summary.json'
URL='https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py'
FIELDS=['event','station','tstar_utc','window_start_utc','window_end_exclusive_utc','window_minutes','hour_obs_10m_kt','pred_10m_kt','height_factor','source_url','http_status','response_rows','valid_minutes','coverage','minute_peak_raw_kt','minute_peak_10m_lower_bound_kt','minute_peak_10m_kt','status','reason','e_hour','e_min','d_kt']

def dt(s): return datetime.fromisoformat(s.replace('Z','+00:00')).astimezone(UTC)
def window(land,tstar):
    start=(land-timedelta(hours=12)).replace(minute=0,second=0,microsecond=0)
    hours={start+timedelta(hours=i) for i in range(24)}
    center=tstar.replace(minute=0,second=0,microsecond=0)
    hours.update(center+timedelta(hours=i) for i in (-2,-1,0,1))
    return min(hours),max(hours)+timedelta(hours=1),len(hours)*60

def work(row,land):
    start,end,n=window(land,dt(row['tstar_utc']))
    q={'station':row['station'],'vars':'sknt','sts':start.strftime('%Y-%m-%dT%H:%MZ'),
       'ets':end.strftime('%Y-%m-%dT%H:%MZ'),'what':'download','tz':'UTC'}
    u=URL+'?'+urllib.parse.urlencode(q)
    d=dict(event=row['event'],station=row['station'],tstar_utc=row['tstar_utc'],
           window_start_utc=start.isoformat(),window_end_exclusive_utc=end.isoformat(),window_minutes=n,
           hour_obs_10m_kt=row['observed_10m_sknt'],pred_10m_kt=row['pred_10m_sknt'],
           height_factor=row['height_factor'],source_url=u,http_status='',response_rows=0,valid_minutes=0,
           coverage=0,minute_peak_raw_kt='',minute_peak_10m_lower_bound_kt='',
           minute_peak_10m_kt='',status='',reason='',e_hour='',e_min='',d_kt='')
    for trial in range(2):
        try:
            request=urllib.request.Request(u,headers={'User-Agent':'PETW-R23.3a-05 observational sampling/1.0'})
            with urllib.request.urlopen(request,timeout=90) as f:
                d['http_status']=f.status; payload=f.read(10_000_000)
            if len(payload)>=10_000_000: raise ValueError('response too large')
            rows=list(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))))
            d['response_rows']=len(rows)
            valid={}
            for r in rows:
                try:
                    stamp=dt(r['valid(UTC)']); sk=float(r['sknt'])
                    if start<=stamp<end and math.isfinite(sk) and sk>=0:
                        valid[stamp.replace(second=0,microsecond=0)]=max(sk,valid.get(stamp.replace(second=0,microsecond=0),-1))
                except (KeyError,TypeError,ValueError): pass
            d['valid_minutes']=len(valid); d['coverage']=len(valid)/n
            if valid:
                d['minute_peak_raw_kt']=max(valid.values())
                d['minute_peak_10m_lower_bound_kt']=max(valid.values())*float(row['height_factor'])
            if not rows: d['status']='unavailable';d['reason']='IEM returned zero rows'
            elif not valid: d['status']='unavailable';d['reason']='no valid sknt minute in window'
            elif d['coverage']<.90: d['status']='minute_censored';d['reason']='valid minute coverage <90%'
            else:
                d['status']='paired';d['minute_peak_10m_kt']=d['minute_peak_10m_lower_bound_kt']
                d['e_hour']=float(row['pred_10m_sknt'])/float(row['observed_10m_sknt'])-1
                d['e_min']=float(row['pred_10m_sknt'])/d['minute_peak_10m_kt']-1
                d['d_kt']=float(row['observed_10m_sknt'])-d['minute_peak_10m_kt']
            return d
        except Exception as exc:
            d['reason']=str(exc);d['status']='fetch_error'
            if trial==0:time.sleep(2)
    return d

def quantile(a,p):
    a=sorted(a); z=(len(a)-1)*p; i=int(z)
    return a[i]+(a[min(i+1,len(a)-1)]-a[i])*(z-i)

def main():
    rows=list(csv.DictReader(SRC.open())); land={r['event']:dt(r['landfall_utc']) for r in csv.DictReader(LAN.open())}
    target=[r for r in rows if r['pool']=='primary' and r['error']!='']
    assert len(target)==69 and len({(r['event'],r['station']) for r in target})==69
    assert all(float(r['observed_10m_sknt'])>0 for r in target)
    print('target',len(target),'first',target[0]['event'],target[0]['station'],flush=True)
    # Durable per-item append; safe if network/provider stalls, and never overwrite.
    with OUT.open('x',newline='') as o,LOG.open('x',newline='') as l:
        w=csv.DictWriter(o,FIELDS); w.writeheader()
        v=csv.DictWriter(l,['event','station','source_url','http_status','response_rows','valid_minutes','status','reason']);v.writeheader()
        with ThreadPoolExecutor(max_workers=6) as ex:
            futures={ex.submit(work,r,land[r['event']]):r for r in target}
            for ix,f in enumerate(as_completed(futures),1):
                d=f.result();w.writerow(d);o.flush()
                v.writerow({k:d[k] for k in v.fieldnames});l.flush()
                print(ix,d['event'],d['station'],d['response_rows'],d['valid_minutes'],d['status'],flush=True)
    saved=list(csv.DictReader(OUT.open()))
    paired=[r for r in saved if r['status']=='paired']
    if paired:
        a=[float(r['e_hour']) for r in paired]; b=[float(r['e_min']) for r in paired]; ds=[float(r['d_kt']) for r in paired]
        metrics=dict(B_hour=statistics.median(a),M_hour=statistics.median(map(abs,a)),
                     B_min=statistics.median(b),M_min=statistics.median(map(abs,b)),
                     d_negative=sum(x<0 for x in ds),d_q1=quantile(ds,.25),d_median=statistics.median(ds),d_q3=quantile(ds,.75))
        metrics['delta_B']=metrics['B_hour']-metrics['B_min'];metrics['delta_M']=metrics['M_hour']-metrics['M_min']
    else:metrics={}
    result=dict(target=len(target),paired=len(paired),status_counts={s:sum(r['status']==s for r in saved) for s in sorted(set(r['status'] for r in saved))},metrics=metrics)
    SUMMARY.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print('SUMMARY',json.dumps(result),flush=True)
if __name__=='__main__':main()
