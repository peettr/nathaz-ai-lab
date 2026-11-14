"""S0 source inventory and METAR screening only. Does not freeze a sample or run AI."""
import csv, datetime as dt, gzip, io, json, math, pathlib, re, tarfile, time
from collections import Counter
from urllib.parse import urlencode
import requests
R=pathlib.Path('/content/r3_s0'); R.mkdir(exist_ok=True)
s=requests.Session(); s.headers['User-Agent']='Academic research (StormCast wind verification)'
with tarfile.open('/content/s0_prior_inputs.tar.gz') as t: t.extractall(R, filter='data')
seen=set()
for name in ['events_verified.csv','r2/events_r2_verified.csv','r2/controls_r2_candidates.csv']:
 for x in csv.DictReader((R/name).open()):
  date=(x.get('peak_utc') or x.get('utc') or '')[:10]
  if date: seen.add((x['station'],date))
for x in json.loads((R/'r2/gust_fit_2022.json').read_text())['cases']:
 seen.add((x['station'],dt.datetime.fromisoformat(x['init']).date().isoformat()))
print('SEEN',len(seen),flush=True)
base='https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/'
index=s.get(base,timeout=45);index.raise_for_status()
all_reports=[]; candidates=[]; summary=Counter()
for year in (2022,2024,2025,2026):
 names=sorted(set(re.findall(r'StormEvents_details-ftp_v1\.0_d'+str(year)+r'_c\d+\.csv\.gz',index.text)))
 assert names,year
 url=base+names[-1]; response=s.get(url,timeout=180);response.raise_for_status()
 print('SOURCE',url,len(response.content),flush=True)
 for x in csv.DictReader(io.StringIO(gzip.decompress(response.content).decode('utf-8-sig'))):
  try:
   raw=dt.datetime.strptime(x['BEGIN_DATE_TIME'],'%d-%b-%y %H:%M:%S')
   tz=re.search(r'([+-]\d{1,2})$',x['CZ_TIMEZONE']); utc=raw-dt.timedelta(hours=int(tz.group(1)))
   lat=float(x['BEGIN_LAT']);lon=float(x['BEGIN_LON'])
  except (ValueError,TypeError,AttributeError,KeyError):continue
  if x['EVENT_TYPE']=='Thunderstorm Wind':all_reports.append((utc.isoformat(),lat,lon,x['EVENT_ID']))
  if x['EVENT_TYPE']!='Thunderstorm Wind' or x['MAGNITUDE_TYPE']!='MG' or float(x.get('MAGNITUDE') or 0)<50:continue
  station=re.match(r'^\(([A-Z0-9]{3})\)',x['BEGIN_LOCATION'])
  if not station or not re.search('ASOS',x['SOURCE']+' '+x['EVENT_NARRATIVE'],re.I):continue
  group='conus' if utc>=dt.datetime(2025,10,1) else 'v1'
  if group=='v1' and (utc<dt.datetime(2022,1,1) or utc>dt.datetime(2025,9,30,23,59) or utc.year==2023 or not (34<=lat<=44 and -102<=lon<=-91)):continue
  if (station.group(1),utc.date().isoformat()) in seen:summary['seen_excluded']+=1;continue
  if not (-126<=lon<=-66 and 24<=lat<=50):continue
  candidates.append(dict(group=group,id=x['EVENT_ID'],station=station.group(1),ncei_utc=utc.isoformat(),ncei_kt=x['MAGNITUDE'],lat=lat,lon=lon,state=x['STATE'],source=x['SOURCE'],ncei_url=url))
  summary[group+'_raw']+=1
 print('YEAR_DONE',year,dict(summary),flush=True)
with (R/'s0_ncei_candidates.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(candidates[0]));w.writeheader();w.writerows(candidates)
(R/'s0_reports.json').write_text(json.dumps(all_reports))
print('CANDIDATES',len(candidates),'REPORTS',len(all_reports),flush=True)
# Small bounded endpoint probe. Never equate this with sample verification.
x=candidates[0]; target=dt.datetime.fromisoformat(x['ncei_utc'])
params=dict(station=x['station'],sts=(target-dt.timedelta(hours=1)).strftime('%Y-%m-%dT%H:%MZ'),ets=(target+dt.timedelta(hours=1)).strftime('%Y-%m-%dT%H:%MZ'),tz='UTC',data='gust,peak_wind_gust,peak_wind_time,metar',format='onlycomma',missing='M',report_type='3,4')
u='https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?'+urlencode(params)
r=s.get(u,timeout=60);r.raise_for_status()
print('METAR_PROBE',x['id'],u,'records',len(list(csv.DictReader(io.StringIO(r.text)))),flush=True)
minute=target.replace(minute=target.minute//5*5,second=0)
radar='https://mesonet.agron.iastate.edu/archive/data/'+minute.strftime('%Y/%m/%d')+'/GIS/uscomp/n0q_'+minute.strftime('%Y%m%d%H%M')+'.png'
r=s.get(radar,timeout=70)
print('RADAR_PROBE',radar,r.status_code,len(r.content),r.headers.get('Content-Type'),flush=True)
(R/'s0_inventory_status.json').write_text(json.dumps(dict(summary=summary,candidate_count=len(candidates),reports=len(all_reports),metar_probe_url=u,radar_probe_url=radar,radar_status=r.status_code,radar_bytes=len(r.content)),indent=2))
print('S0_INVENTORY_DONE',flush=True)
