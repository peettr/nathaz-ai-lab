"""Recheck separate TS and gust reports among previously failed 21 cases."""
import csv,datetime as dt,json,re,requests
from concurrent.futures import ThreadPoolExecutor
rows=[json.loads(l) for l in open('/content/s0_metar_checked.jsonl')]
extra=[x for x in rows if x['status']=='metar_fail' and x.get('ts_reports') and x.get('max_kt') is not None and x['max_kt']>=50]
def query(x):
 resp=requests.get(x['iem_url'],timeout=60);resp.raise_for_status();rec=list(csv.DictReader(resp.text.splitlines()));target=dt.datetime.fromisoformat(x['ncei_utc']);ts=[];gust=[]
 for v in rec:
  if re.search(r'\b(?:\+|-)?TS[A-Z]*\b|\bVCTS\b',v.get('metar','')):ts.append(v['valid'])
  for fld,tfield in [('gust','valid'),('peak_wind_gust','peak_wind_time')]:
   try:
    t=dt.datetime.strptime(v[tfield],'%Y-%m-%d %H:%M');speed=float(v[fld])
    if speed>=50 and abs((t-target).total_seconds())<=3600:gust.append(dict(utc=t.isoformat(),kt=speed,metar=v['metar'],field=fld,report_utc=v['valid']))
   except (TypeError,ValueError,KeyError):pass
 if not ts or not gust:return None
 best=max(gust,key=lambda y:(y['kt'],-abs((dt.datetime.fromisoformat(y['utc'])-target).total_seconds())))
 return {**x,'status':'metar_pass_separate','hit':best,'ts_times':ts,'iem_rows':len(rec)}
with ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(query,extra))
with open('/content/s0_metar_extra.jsonl','x') as f:
 for x in results:
  if x:f.write(json.dumps(x)+'\n')
print('EXTRA',len(extra),sum(x is not None for x in results),flush=True)
