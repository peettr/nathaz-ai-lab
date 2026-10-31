"""Frozen C station-stage test; execute only on Colab CPU. Results are compact."""
import csv,io,json,gzip,re,math,time,os,calendar,datetime as dt,urllib.parse,urllib.request,traceback
from pathlib import Path
from collections import defaultdict
import numpy as np
ROOT=Path(os.environ.get('SITE_STAGE_ROOT','/content/site_stage_test'));ROOT.mkdir(exist_ok=True)
STATIONS=['KDSM','KOMA','KFAR','KIND','KBDL']; EXTRA=['KFSD','KICT']; ALL=STATIONS+EXTRA
GRID={'KDSM':(131,266),'KOMA':(131,264),'KFAR':(137,263),'KIND':(129,273),'KBDL':(132,287),'KFSD':(133,263),'KICT':(127,262)}
CO={'KDSM':('POLK','IOWA'),'KOMA':('DOUGLAS','NEBRASKA'),'KFAR':('CASS','NORTH DAKOTA'),'KIND':('MARION','INDIANA'),'KBDL':('HARTFORD','CONNECTICUT'),'KFSD':('MINNEHAHA','SOUTH DAKOTA'),'KICT':('SEDGWICK','KANSAS')}
# HOMR coordinates, supplied as compact source-derived metadata; not used to select test sites.
COORD={'KDSM':(41.534,-93.663),'KOMA':(41.302,-95.894),'KFAR':(46.9207,-96.8158),'KIND':(39.7173,-86.2944),'KBDL':(41.9386,-72.6880),'KFSD':(43.5855,-96.7412),'KICT':(37.6503,-97.4286)}
HEAD={'User-Agent':'PETW-AIWeather-station-stage/1.0'}
def fetch(url):
 for k in range(4):
  try:return urllib.request.urlopen(urllib.request.Request(url,headers=HEAD),timeout=180)
  except Exception:
   if k==3:raise
   time.sleep(3*(k+1))
def stamp(t):return t.strftime('%Y-%m-%dT%H:%MZ')
def parse(s):
 try:return dt.datetime.fromisoformat(s.strip().replace(' ','T').replace('Z','+00:00')).replace(tzinfo=None)
 except:return None
def num(s):
 try:
  x=float(s)
  return x if np.isfinite(x) and 0<=x<300 else None
 except:return None
def query(st,a,b,fields='gust,peak_wind_gust,peak_wind_time,wxcodes,metar',kind='metar'):
 if kind=='metar':
  q={'station':st[1:],'data':fields,'sts':stamp(a),'ets':stamp(b),'tz':'UTC','report_type':'3,4','format':'onlycomma','missing':'M'}
  base='https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?'
 else:
  q={'station':st[1:],'vars':fields,'sts':stamp(a),'ets':stamp(b),'tz':'UTC','what':'download'}
  base='https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py?'
 return base+urllib.parse.urlencode(q)
def raw_parts(raw):
 # Trim remarks: TSNO in remarks is explicitly NOT a thunderstorm. METAR token groups and cloud groups only.
 s=(raw or '').upper();s=s.split(' RMK ')[0];return re.split(r'\s+',s)
def convcode(raw,wx):
 toks=raw_parts(raw)+re.split('[,; ]+',str(wx or '').upper())
 return any((re.match(r'^[+-]?(?:VC)?TS(?:RA|SN|GR|GS|PL|DZ|UP)*$',t) or t in ('SQ','FC','+FC') or re.match(r'^(?:FEW|SCT|BKN|OVC)\d{3}CB$',t)) for t in toks if t!='TSNO')
def routine(raw):
 p=raw_parts(raw)
 return len(p)>2 and p[0] in ('METAR','SPECI') and p[1] and p[0]=='METAR' or (len(p)>1 and p[0].startswith('K') and re.match(r'^\d{6}Z$',p[1] or '') is not None)
def peak_time(row):
 t=parse(row.get('peak_wind_time',''))
 if t:return t
 # IEM may already report actual peak time as a UTC ISO string; unresolved otherwise.
 return None
def load_obs(st,y):
 a=dt.datetime(y,10,1);b=dt.datetime(y+1,4,1);url=query(st,a,b)
 with fetch(url) as r:rows=list(csv.DictReader(io.TextIOWrapper(r,encoding='utf8',errors='replace')))
 # IEM report_type=3 is routine only; 4 is specials; 1 is MADIS five-minute HFMETAR, never include it.
 ru=query(st,a,b,fields='metar');ru=ru.replace('report_type=3%2C4','report_type=3')
 with fetch(ru) as r:rout=list(csv.DictReader(io.TextIOWrapper(r,encoding='utf8',errors='replace')))
 regular_times={t for r in rout if (t:=parse(r.get('valid',''))) and a<=t<b}
 regular={t.replace(minute=0,second=0) for t in regular_times}
 reports=[];candidates=[]
 for r in rows:
  t=parse(r.get('valid',''))
  if not t or not a<=t<b:continue
  raw=r.get('metar') or '';is_regular=t in regular_times and not raw.startswith('SPECI ')
  rr={'time':t,'raw':raw,'wx':r.get('wxcodes') or '', 'regular':is_regular};reports.append(rr)
  for key,src in [('gust','gust'),('peak_wind_gust','pk')]:
   v=num(r.get(key))
   if v is None:continue
   event_t=peak_time(r) if src=='pk' else t
   if event_t is None:continue
   if not a<=event_t<b:continue
   candidates.append({'time':event_t,'value':v,'source':src,'report_time':t,'raw':raw})
 reports.sort(key=lambda r:r['time'])
 expected=int((b-a).total_seconds()/3600)
 return {'st':st,'y':y,'reports':reports,'regular':regular,'coverage':len(regular)/expected,'expected_hours':expected,'candidates':candidates,'url':url}
def storm_data():
 path=ROOT/'storms.json'
 if path.exists():return json.loads(path.read_text())
 base='https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/'
 html=fetch(base).read().decode();names=sorted(set(re.findall(r'StormEvents_details-ftp_v1\.0_d\d{4}_c\d{8}\.csv\.gz',html)))
 urls={int(re.search(r'_d(\d{4})_',n).group(1)):base+n for n in names};assert all(y in urls for y in range(2000,2023))
 out=[]
 offsets={'CST':-6,'EST':-5,'MST':-7,'PST':-8,'AKST':-9,'HST':-10}
 for y in range(2000,2023):
  with fetch(urls[y]) as resp,gzip.GzipFile(fileobj=resp) as gz:
   for r in csv.DictReader(io.TextIOWrapper(gz,encoding='utf-8-sig',errors='replace')):
    typ=r.get('EVENT_TYPE','');county=r.get('CZ_NAME','').upper();state=r.get('STATE','').upper()
    if typ not in ('Thunderstorm Wind','Tornado','Hail','Hurricane (Typhoon)','Tropical Storm','Tropical Depression'):continue
    sts=[s for s in ALL if (county,state)==CO[s] and r.get('CZ_TYPE','')=='C']
    if not sts:continue
    z=(r.get('CZ_TIMEZONE') or '').upper();m=re.search(r'[+-]\d+',z);off=int(m.group()) if m else offsets.get(z)
    if off is None:raise ValueError(('unknown storm timezone',z,y))
    def convert(v):
     for fmt in ('%d-%b-%y %H:%M:%S','%d-%b-%y %H:%M','%m/%d/%Y %H:%M:%S','%m/%d/%Y %H:%M'):
      try:return dt.datetime.strptime(v,fmt)-dt.timedelta(hours=off)
      except ValueError:pass
     raise ValueError(('storm time',v))
    try:t0=convert(r['BEGIN_DATE_TIME']);t1=convert(r['END_DATE_TIME'])
    except ValueError:continue
    for s in sts:out.append({'station':s,'type':typ,'start':stamp(t0),'end':stamp(t1),'event_id':r.get('EVENT_ID'),'url':urls[y]})
  print('STORM',y,len(out),flush=True)
 path.write_text(json.dumps(out));return out
def tracks():
 path=ROOT/'tracks.json'
 if path.exists():return json.loads(path.read_text())
 url='https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2025-092326.txt';out=[];name=''
 for line in fetch(url).read().decode('ascii','replace').splitlines():
  x=[v.strip() for v in line.split(',')]
  if re.match(r'AL\d{6}$',x[0]):name=x[1];continue
  if len(x)<8:continue
  try:
   t=dt.datetime.strptime(x[0]+x[1],'%Y%m%d%H%M')
   if not 2000<=t.year<=2022:continue
   la=float(x[4][:-1])*(-1 if x[4][-1]=='S' else 1);lo=float(x[5][:-1])*(-1 if x[5][-1]=='W' else 1)
   out.append({'time':stamp(t),'lat':la,'lon':lo,'name':name,'status':x[3],'url':url})
  except:pass
 path.write_text(json.dumps(out));return out
def distance(a,b):
 p,q,r,s=map(math.radians,(*a,*b));h=math.sin((r-p)/2)**2+math.cos(p)*math.cos(r)*math.sin((s-q)/2)**2
 return 12742*math.asin(min(1,math.sqrt(h)))
def label(c,obs,storms,track):
 t=c['time'];close=[r for r in obs['reports'] if abs((r['time']-t).total_seconds())<=3600]
 front=any(r['regular'] and t-dt.timedelta(minutes=90)<=r['time']<t for r in obs['reports'])
 back=any(r['regular'] and t<r['time']<=t+dt.timedelta(minutes=90) for r in obs['reports'])
 if not front or not back:return 'unknown',{'reason':'regular_metar_90min_missing'}
 conv=[r['time'] for r in close if convcode(r['raw'],r['wx'])]
 ev=[e for e in storms if e['station']==obs['st'] and parse(e['start'])-dt.timedelta(hours=1)<=t<=parse(e['end'])+dt.timedelta(hours=1)]
 hit=[e for e in ev if e['type'] in ('Thunderstorm Wind','Tornado','Hail')]
 tc=[e for e in ev if e['type'] in ('Hurricane (Typhoon)','Tropical Storm','Tropical Depression')]
 fixes=[f for f in track if abs((parse(f['time'])-t).total_seconds())<=10800 and distance(COORD[obs['st']],(f['lat'],f['lon']))<=500]
 evidence={'metar_conv_utc':[stamp(z) for z in conv],'event_ids':[e['event_id'] for e in ev],'nhc_names':[f['name'] for f in fixes]}
 return ('convection' if conv or hit else 'tropical' if tc or fixes else 'nonconvective'),evidence
def obs_stage():
 path=ROOT/'station_seasons.jsonl';done={}
 if path.exists():
  for s in path.read_text().splitlines():
   x=json.loads(s);done[(x['station'],x['season_year'])]=x
 storm=storm_data();track=tracks();SE=defaultdict(list);TR=defaultdict(list)
 for x in storm:SE[x['station']].append(x)
 for x in track:TR[int(x['time'][:4])].append(x)
 for y in range(2000,2022):
  for st in ALL:
   if (st,y) in done:continue
   obs=load_obs(st,y)
   ranked=sorted(obs['candidates'],key=lambda c:(-c['value'],c['time']))
   count=defaultdict(int);selected=None;evs=SE[st];fixes=TR[y]+TR[y+1]
   for c in ranked:
    lab,evidence=label(c,obs,evs,fixes);count[lab]+=1
    if lab=='nonconvective':selected={'kn':c['value'],'event_utc':stamp(c['time']),'source':c['source'],'report_utc':stamp(c['report_time']),'raw':c['raw'],'evidence':evidence};break
   out={'station':st,'season_year':y,'season':f'{y}/{str(y+1)[-2:]}','coverage':obs['coverage'],'hours_covered':len(obs['regular']),'expected_hours':obs['expected_hours'],'report_count':len(obs['reports']),'candidate_count':len(ranked),'screen_count':dict(count),'peak':selected,'metar_url':obs['url']}
   with path.open('a') as fp:fp.write(json.dumps(out,ensure_ascii=False)+'\n');fp.flush();os.fsync(fp.fileno())
   print('OBS',st,y,round(out['coverage'],3),selected and selected['kn'],dict(count),flush=True)
   time.sleep(.3)
 (ROOT/'obs.done').write_text(json.dumps({'rows':sum(1 for _ in path.open()),'years':'2000-2021'}))
if __name__=='__main__':
 import sys
 try:
  if sys.argv[1]=='obs':obs_stage()
  else:raise ValueError(sys.argv)
 except Exception:
  (ROOT/'error.log').write_text(traceback.format_exc());raise
