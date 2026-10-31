"""Audit 21 separate METAR TS/gust reports and 9 fitted NCEI dates; append only."""
import csv,datetime as dt,gzip,io,json,re,requests,tarfile
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor
root='/content/'; prior='/content/prior'; import os;os.makedirs(prior,exist_ok=True)
with tarfile.open(root+'s0_prior_inputs.tar.gz') as f:f.extractall(prior,filter='data')
fit=json.load(open(prior+'/r2/gust_fit_2022.json'))['cases']; ids={x['id'] for x in fit}
u='https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/StormEvents_details-ftp_v1.0_d2022_c20260918.csv.gz'
# Actual source used by inventory may differ. Retrieve from candidate's URL.
a=[json.loads(l) for l in open(root+'s0_metar_checked.jsonl')];u=next(x['ncei_url'] for x in a if x['group']=='v1' and x['ncei_url'].find('_d2022_')>0)
r=requests.get(u,timeout=180);r.raise_for_status();frows=list(csv.DictReader(io.StringIO(gzip.decompress(r.content).decode('utf-8-sig')))); dates=[]
for x in frows:
 if x['EVENT_ID'] not in ids:continue
 t=dt.datetime.strptime(x['BEGIN_DATE_TIME'],'%d-%b-%y %H:%M:%S');z=re.search(r'([+-]\d{1,2})$',x['CZ_TIMEZONE']);
 if not z:raise ValueError(x['CZ_TIMEZONE'])
 t=t-dt.timedelta(hours=int(z.group(1)));dates.append(dict(id=x['EVENT_ID'],station=next(k['station'] for k in fit if k['id']==x['EVENT_ID']),utc=t.isoformat(),source=u))
print('FIT_ACTUAL',len(dates),dates,flush=True)
json.dump(dates,open(root+'s0_fit_actual.json','w'))
extra=[x for x in a if x['status']=='metar_fail' and x.get('ts_reports') and x.get('max_kt') is not None and x['max_kt']>=50]
def query(x):
 resp=requests.get(x['iem_url'],timeout=60);resp.raise_for_status();rec=list(csv.DictReader(resp.text.splitlines()));target=dt.datetime.fromisoformat(x['ncei_utc']);ts=[];gust=[]
 for v in rec:
  if re.search(r'\b(?:\+|-)?TS[A-Z]*\b|\bVCTS\b',v.get('metar','')):ts.append(v['valid'])
  for field,timefield in [('gust','valid'),('peak_wind_gust','peak_wind_time')]:
   try:
    t=dt.datetime.strptime(v[timefield],'%Y-%m-%d %H:%M');speed=float(v[field]);
    if speed>=50 and abs((t-target).total_seconds())<=3600:gust.append(dict(utc=t.isoformat(),kt=speed,metar=v['metar'],field=field,report_utc=v['valid']))
   except (TypeError,ValueError,KeyError):pass
 if not ts or not gust:return None
 best=max(gust,key=lambda y:(y['kt'],-abs((dt.datetime.fromisoformat(y['utc'])-target).total_seconds())))
 return dict(**x,status='metar_pass_separate',hit=best,ts_times=ts,iem_rows=len(rec))
with ThreadPoolExecutor(max_workers=6) as pool: results=list(pool.map(query,extra))
with open(root+'s0_metar_extra.jsonl','w') as f:
 for x in results:
  if x:f.write(json.dumps(x)+'\n')
print('EXTRA',len(extra),sum(x is not None for x in results),flush=True)
