"""S0 METAR crosscheck of NCEI prescreen, append-only per candidate."""
import csv,datetime as dt,json,pathlib,re,time,requests
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor,as_completed
R=pathlib.Path('/content/r3_s0'); rows=list(csv.DictReader((R/'s0_ncei_candidates.csv').open()))
fit_ids={x['id'] for x in json.loads((R/'r2/gust_fit_2022.json').read_text())['cases']}
rows=[x for x in rows if x['id'] not in fit_ids]
out=R/'s0_metar_checked.jsonl'; assert not out.exists()
s=requests.Session(); s.headers['User-Agent']='Academic research StormCast validation'
def run(x):
 t=dt.datetime.fromisoformat(x['ncei_utc']);u='https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?'+urlencode(dict(station=x['station'],sts=(t-dt.timedelta(hours=1)).strftime('%Y-%m-%dT%H:%MZ'),ets=(t+dt.timedelta(hours=1)).strftime('%Y-%m-%dT%H:%MZ'),tz='UTC',data='gust,peak_wind_gust,peak_wind_time,metar',format='onlycomma',missing='M',report_type='3,4'))
 try:
  resp=s.get(u,timeout=45);resp.raise_for_status();rec=list(csv.DictReader(resp.text.splitlines()))
  hits=[];allwinds=[];ts=[]
  for a in rec:
   report=a.get('metar',''); valid=a.get('valid','');
   if re.search(r'\b(?:\+|-)?TS[A-Z]*\b|\bVCTS\b',report):ts.append(valid)
   for fld,stamp in [('gust','valid'),('peak_wind_gust','peak_wind_time')]:
    try:
     kt=float(a[fld]);windtime=dt.datetime.strptime(a[stamp],'%Y-%m-%d %H:%M')
     if abs((windtime-t).total_seconds())>3600:continue
     allwinds.append(kt)
     if kt>=50 and re.search(r'\b(?:\+|-)?TS[A-Z]*\b|\bVCTS\b',report): hits.append(dict(kt=kt,utc=windtime.isoformat(),metar=report,field=fld,report_utc=valid))
    except (KeyError,TypeError,ValueError):pass
  return dict(**x,iem_url=u,iem_rows=len(rec),max_kt=max(allwinds) if allwinds else None,ts_reports=len(ts),ts_times=ts,status='metar_pass' if hits else 'metar_fail',hit=max(hits,key=lambda z:z['kt']) if hits else None)
 except Exception as e:return dict(**x,iem_url=u,status='error',error=repr(e))
start=time.monotonic(); counts={}
with ThreadPoolExecutor(max_workers=6) as pool, out.open('x') as f:
 for j,result in enumerate(pool.map(run,rows),1):
  f.write(json.dumps(result)+'\n');f.flush();counts[result['status']]=counts.get(result['status'],0)+1
  if j%25==0:print('PROGRESS',j,len(rows),counts,'minutes',round((time.monotonic()-start)/60,2),flush=True)
print('METAR_DONE',len(rows),counts,flush=True)
