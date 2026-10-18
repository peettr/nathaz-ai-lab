"""Frozen station QC before any ERA5 pairing; execute in Colab CPU only.
NCEI global-hourly OC1 is gust; WND is sustained, NEVER compare WND to gust.
"""
import os,sys,csv,json,re,io,urllib.request,urllib.parse,datetime as dt,traceback,time,math
from pathlib import Path
from collections import defaultdict,Counter
os.environ['SITE_STAGE_ROOT']='/content/site_stage_qc'
sys.path.insert(0,'/content')
import run_colab as core
ROOT=Path('/content/site_stage_qc');ROOT.mkdir(exist_ok=True)
META={r['station']:r for r in csv.DictReader((ROOT/'static_gates.csv').open())}
ADM=[r for r in csv.DictReader((ROOT/'station_admission.csv').open()) if r['admitted']=='true']
assert len(ADM)==29 and Counter(r['region'] for r in ADM)=={'plains':18,'other':11}
core.ALL=list(META);core.CO={r['station']:(r['county'].upper(),{'MN':'MINNESOTA','ND':'NORTH DAKOTA','SD':'SOUTH DAKOTA','IA':'IOWA','NE':'NEBRASKA','KS':'KANSAS','MO':'MISSOURI','OK':'OKLAHOMA','IL':'ILLINOIS','NY':'NEW YORK','OH':'OHIO','MI':'MICHIGAN','PA':'PENNSYLVANIA','IN':'INDIANA','KY':'KENTUCKY','TN':'TENNESSEE','WV':'WEST VIRGINIA','VA':'VIRGINIA','NC':'NORTH CAROLINA','SC':'SOUTH CAROLINA','GA':'GEORGIA','AL':'ALABAMA','MS':'MISSISSIPPI','AR':'ARKANSAS','LA':'LOUISIANA','TX':'TEXAS','CT':'CONNECTICUT','WI':'WISCONSIN'}.get(r['state'],r['state'])) for r in META.values()}
core.COORD={r['station']:(float(r['lat']),float(r['lon'])) for r in META.values()}
UTC=dt.timezone.utc
STATIONS=[r['station'] for r in ADM]
# Official station history uses USAF + WBAN. Retain every candidate identifier.
history=urllib.request.urlopen('https://www.ncei.noaa.gov/pub/data/noaa/isd-history.csv',timeout=120).read().decode('utf-8-sig')
H=defaultdict(list)
for r in csv.DictReader(io.StringIO(history)):
 st=r.get('ICAO','').strip()
 if st in STATIONS and r.get('USAF','')!='999999' and r.get('WBAN','')!='99999':H[st].append((r['USAF']+r['WBAN'],r.get('END','')))
assert all(H[s] for s in STATIONS)
(ROOT/'isd_station_ids.json').write_text(json.dumps(H,indent=2))
# v2 sources, as previously frozen, for weather screening.
print('STORMS START',flush=True)
storm=core.storm_data();track=core.tracks();SE=defaultdict(list);TR=defaultdict(list)
for e in storm:SE[e['station']].append(e)
for e in track:TR[int(e['time'][:4])].append(e)
print('STORMS READY',len(storm),len(track),flush=True)
ISD={}
def isd(st,t):
 key=(st,t.strftime('%Y-%m-%d'))
 if key not in ISD:
  ids=sorted(H[st],key=lambda z:z[1],reverse=True)
  chosen=ids[0][0]
  url='https://www.ncei.noaa.gov/access/services/data/v1?'+urllib.parse.urlencode({'dataset':'global-hourly','stations':chosen,'startDate':key[1],'endDate':key[1],'format':'json','includeAttributes':'true'})
  err=None
  for i in range(3):
   try:
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'PETW-station-QC/1.0'}),timeout=60) as z:raw=z.read()
    rows=json.loads(raw);ISD[key]=(rows,url,raw);break
   except Exception as ex:err=str(ex);time.sleep(2*(i+1))
  else:raise RuntimeError(('ISD fetch failed',key,err))
 rows,url,raw=ISD[key];close=[]
 for r in rows:
  z=core.parse(r.get('DATE',''))
  if z and abs((z-t).total_seconds())<=600:close.append((abs((z-t).total_seconds()),r))
 close.sort(key=lambda a:a[0]);return close,url,raw
WIND_RE=re.compile(r'\b(?:\d{3}|VRB)(\d{2,3})G(\d{2,3})KT\b')
SUST_RE=re.compile(r'\b(?:\d{3}|VRB)(\d{2,3})(?:G\d{2,3})?KT\b')
PK_RE=re.compile(r'\bPK\s+WND\s+\d{3}(\d{2,3})/\d{4}\b')
def raw_wind(raw,source):
 s=(raw or '').upper();m=PK_RE.search(s) if source=='pk' else WIND_RE.search(s)
 return int(m.group(1) if source=='pk' else m.group(2)) if m else None
def raw_sust(raw):
 m=SUST_RE.search((raw or '').upper());return int(m.group(1)) if m else None
def q5(st,c):
 close,url,raw=isd(st,c['time'])
 # OC1 is the NCEI wind-gust observation (m/s x 10, quality code), not WND.
 found=[(d,r) for d,r in close if r.get('OC1') and r['OC1'].split(',')[0].isdigit() and r['OC1'].split(',')[0]!='9999']
 if not found:return 'ISD 未核',None,None,url,raw
 d,r=min(found,key=lambda a:a[0]);parts=r['OC1'].split(',');qc=parts[1] if len(parts)>1 else '9';v=float(parts[0])/10/0.514444
 info={'isd_time':r['DATE'],'OC1':r['OC1'],'WND':r.get('WND'),'source':r.get('SOURCE'),'isd_kn':v,'delta_sec':d}
 if qc in ('2','3','6','7'):return 'ISD 可疑/错误',None,info,url,raw
 if abs(v-c['value'])>2:return 'ISD 更正',v,info,url,raw
 return 'ISD 一致',c['value'],info,url,raw
out=ROOT/'qc_station_seasons.jsonl';log=ROOT/'qc_log.csv';rawmanifest=ROOT/'raw_manifest.jsonl'
assert not out.exists() and not log.exists(), 'exclusive outputs must be new'
logfp=log.open('x',newline='');writer=csv.DictWriter(logfp,fieldnames=['generated_edt','station','season_year','report_utc','event_utc','source','original_kn','raw','rules','isd_status','isd_oc1']);writer.writeheader();logfp.flush()
def edt():return dt.datetime.now(dt.timezone(dt.timedelta(hours=-4))).isoformat()
for st in STATIONS:
 for y in range(2007,2022):
  try:
   obs=core.load_obs(st,y);cs=sorted(obs['candidates'],key=lambda c:(-c['value'],c['time']));n=Counter();selected=None;original=None;loop=0;rawurls=[]
   if cs:original={'kn':cs[0]['value'],'event_utc':core.stamp(cs[0]['time']),'source':cs[0]['source']}
   for c in cs:
    # Mechanism and completeness remain identical to frozen v2; QC checks every report, not just the winner.
    rules=[];v=c['value'];raw=c['raw'];parsed=raw_wind(raw,c['source']);sust=raw_sust(raw)
    if v>100:rules.append('Q1')
    if v!=int(v):
     if parsed is None:rules.append('Q2')
     else:v=float(parsed);n['Q2_reparsed']+=1
    if sust is not None and v-sust>40:rules.append('Q3')
    others=[z['value'] for z in cs if z is not c and z['report_time']!=c['report_time'] and abs((z['time']-c['time']).total_seconds())<=10800]
    # Sustained winds of other reports: load_obs reports lacks speed, so read raw METAR on its report records.
    others += [w for z in obs['reports'] if abs((z['time']-c['time']).total_seconds())<=10800 and z['time']!=c['report_time'] if (w:=raw_sust(z['raw'])) is not None]
    if others and v-max(others)>30:rules.append('Q4')
    if rules:
     for z in rules:n[z]+=1
     writer.writerow(dict(generated_edt=edt(),station=st,season_year=y,report_utc=core.stamp(c['report_time']),event_utc=core.stamp(c['time']),source=c['source'],original_kn=c['value'],raw=raw,rules=';'.join(rules),isd_status='',isd_oc1=''));continue
    c2=dict(c,value=v)
    lab,evidence=core.label(c2,obs,SE[st],TR[y]+TR[y+1]);n['mechanism_'+lab]+=1
    if lab!='nonconvective':continue
    if loop>=5:n['Q5_unresolved']+=1;break
    loop+=1
    status,new,info,url,rawisd=q5(st,c2);n[status]+=1
    if status=='ISD 可疑/错误':
     writer.writerow(dict(generated_edt=edt(),station=st,season_year=y,report_utc=core.stamp(c['report_time']),event_utc=core.stamp(c['time']),source=c['source'],original_kn=c['value'],raw=raw,rules='Q5',isd_status=status,isd_oc1=info['OC1']));continue
    if status=='ISD 更正':
     # For a replacement to remain the season maximum, compare with all other already Q1–Q4-passing, nonconvective candidates.
     c2['value']=new
     larger=False
     for competitor in cs:
      if competitor is c or competitor['value']<=new:continue
      # Only a previously passed candidate can outrank; scan in descending rank; ones above current were already rejected.
      if competitor['value']<c['value']:larger=True;break
     if larger:
      n['Q5_replaced_not_max']+=1
      continue
    selected={'kn':new,'event_utc':core.stamp(c['time']),'report_utc':core.stamp(c['report_time']),'source':c['source'],'original_kn':c['value'],'raw':raw,'evidence':evidence,'isd_status':status,'isd_info':info,'isd_url':url};break
   valid=obs['coverage']>=.9 and selected is not None and not n['Q5_unresolved']
   row={'station':st,'season_year':y,'coverage':obs['coverage'],'original_peak':original,'qc_peak':selected,'valid':valid,'rule_counts':dict(n),'q5_loops':loop,'metar_url':obs['url'],'generated_edt':edt()}
   with rawmanifest.open('a') as f:
    f.write(json.dumps({'station':st,'season_year':y,'iem_url':obs['url'],'isd_urls':sorted({v[1] for k,v in ISD.items() if k[0]==st})})+'\n')
  except Exception as ex:
   row={'station':st,'season_year':y,'valid':False,'error':repr(ex),'trace':traceback.format_exc()[-1000:],'generated_edt':edt()}
  with out.open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
  logfp.flush();print('QC',st,y,row.get('valid'),row.get('qc_peak',{}),row.get('error',''),flush=True)
 logfp.flush()
logfp.close()
assert sum(1 for _ in out.open())==435
errors=[json.loads(line) for line in out.open() if '"error"' in line]
(ROOT/'qc.done').write_text(json.dumps({'generated_edt':edt(),'rows':435,'errors':len(errors),'error_keys':[(r['station'],r['season_year']) for r in errors]}))
print('QC_DONE',len(errors),flush=True)
