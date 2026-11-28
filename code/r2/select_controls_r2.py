"""Find matched station/time controls with no local Storm Events or IEM gust."""
import csv,datetime as dt,gzip,io,math,pathlib,requests,re,urllib.parse,urllib.request
ROOT=pathlib.Path(__file__).parent
positive=list(csv.DictReader((ROOT/'events_r2_verified.csv').open(newline='')))
idx=requests.get('https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/',timeout=60).text
name=sorted(set(re.findall(r'StormEvents_details-ftp_v1\.0_d2023_c\d+\.csv\.gz',idx)))[-1]
url='https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/'+name
resp=requests.get(url,timeout=120);resp.raise_for_status()
rows=list(csv.DictReader(io.StringIO(gzip.decompress(resp.content).decode('utf-8-sig'))))
reports=[]
for r in rows:
 try:
  if r['EVENT_TYPE'] not in ('Thunderstorm Wind','High Wind','Strong Wind','Tornado','Hail'):continue
  lat=float(r['BEGIN_LAT']);lon=float(r['BEGIN_LON'])
  tm=dt.datetime.strptime(r['BEGIN_DATE_TIME'],'%d-%b-%y %H:%M:%S')
  tz=re.search(r'([+-]\d{1,2})$',r['CZ_TIMEZONE']);tm-=dt.timedelta(hours=int(tz.group(1)))
  reports.append((tm,lat,lon,r['EVENT_TYPE']))
 except (ValueError,TypeError,AttributeError):pass
print('STORM_REPORTS',len(reports),url,flush=True)
def km(a,b,c,d):
 a,c=math.radians(a),math.radians(c); z=math.sin((c-a)/2)**2+math.cos(a)*math.cos(c)*math.sin(math.radians(d-b)/2)**2
 return 12742*math.asin(min(1,math.sqrt(z)))
def wind(station,t):
 p={'station':station,'sts':(t-dt.timedelta(hours=3)).strftime('%Y-%m-%dT%H:%MZ'),'ets':(t+dt.timedelta(hours=3)).strftime('%Y-%m-%dT%H:%MZ'),'tz':'UTC','data':'gust,peak_wind_gust,peak_wind_time,metar','format':'onlycomma','missing':'M','report_type':'3,4'}
 u='https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?'+urllib.parse.urlencode(p)
 with urllib.request.urlopen(u,timeout=50) as f:r=list(csv.DictReader(io.StringIO(f.read().decode('utf-8-sig'))))
 vals=[float(x[k]) for x in r for k in ('gust','peak_wind_gust') if x.get(k) not in ('','M',None)]
 return (max(vals) if vals else None),len(r),u
out=[];dates=set();
for p in positive:
 if p['group']!='v1' or len(out)>=12:continue
 t=dt.datetime.fromisoformat(p['utc'])-dt.timedelta(days=7)
 if t.date() in dates:continue
 a,b=float(p['lat']),float(p['lon'])
 near=[r for r in reports if abs((r[0]-t).total_seconds())<=3*3600 and km(a,b,r[1],r[2])<=50]
 if near:continue
 try:
  maxgust,n,u=wind(p['station'],t)
  if n<5 or maxgust is None or maxgust>=40:continue
  out.append(dict(group='control',id='C'+p['id'],station=p['station'],utc=t.isoformat(),obs_kt=maxgust,lat=p['lat'],lon=p['lon'],state=p['state'],year=2023,ncei_url=url,iem_url=u,metar='',qc='NO_NCEI_STORM_REPORT_WITHIN_50KM_3H;IEM_MAX_GUST_LT40KT;MESONET_PENDING',selection='same_station_time_minus_7_days',iem_rows=n))
  dates.add(t.date());print('CONTROL_CANDIDATE',out[-1]['id'],t,maxgust,n,flush=True)
 except Exception as e:print('ERROR',p['id'],repr(e),flush=True)
if out:
 with (ROOT/'controls_r2_candidates.csv').open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=out[0]);w.writeheader();w.writerows(out)
print('COUNT',len(out),flush=True)
