"""Select distinct measured-ASOS thunderstorm wind days, reproducibly."""
import csv,gzip,io,re,requests,datetime as dt,collections,random,pathlib
ROOT=pathlib.Path(__file__).parent
BASE='https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/'
index=requests.get(BASE,timeout=60).text
candidates=[]
for year in (2023,2024):
 names=sorted(set(re.findall(r'StormEvents_details-ftp_v1\.0_d'+str(year)+r'_c\d+\.csv\.gz',index)))
 name=names[-1]; data=requests.get(BASE+name,timeout=180).content
 print('SOURCE',name,'bytes',len(data),flush=True)
 (ROOT/('source_'+str(year)+'.url')).write_text(BASE+name+'\n')
 rows=csv.DictReader(io.StringIO(gzip.decompress(data).decode('utf-8-sig')))
 for r in rows:
  if r['EVENT_TYPE']!='Thunderstorm Wind' or r['MAGNITUDE_TYPE']!='MG' or r['SOURCE'].strip().upper()!='ASOS':continue
  try:
   gust=float(r['MAGNITUDE']);lat=float(r['BEGIN_LAT']);lon=float(r['BEGIN_LON'])
   if gust<50 or not (25<=lat<=49 and -125<=lon<=-67):continue
   station=re.match(r'^\(([A-Z0-9]{3})\)',r['BEGIN_LOCATION'])
   if not station:continue
   raw=dt.datetime.strptime(r['BEGIN_DATE_TIME'],'%d-%b-%y %H:%M:%S')
   tz=re.search(r'([+-]\d{1,2})$',r['CZ_TIMEZONE'])
   if not tz:continue
   utc=raw-dt.timedelta(hours=int(tz.group(1)))
   candidates.append(dict(event_id=r['EVENT_ID'],station=station.group(1),utc=utc,lat=lat,lon=lon,gust=gust,state=r['STATE'],location=r['BEGIN_LOCATION'],source_url=BASE+name,source=r['SOURCE'],narrative=r['EVENT_NARRATIVE']))
  except (ValueError,KeyError):continue
# One event per UTC day; retain most intense ASOS measurement per day, then deterministic spread across months.
byday={}
for c in candidates:
 day=c['utc'].date()
 if day not in byday or (c['gust'],c['event_id'])>(byday[day]['gust'],byday[day]['event_id']):byday[day]=c
pool=list(byday.values());pool.sort(key=lambda x:(x['utc'].month,x['utc'].year,x['utc'].date(),x['event_id']))
monthly=collections.defaultdict(list)
for c in pool:monthly[c['utc'].month].append(c)
selected=[]
# Round robin month in order, rotating years and state by ordering dates; take 40.
while len(selected)<40 and any(monthly.values()):
 for month in sorted(monthly):
  if monthly[month] and len(selected)<40:
   # highest measured gust among currently unrepresented states, then rotate states
   used={x['state'] for x in selected if x['utc'].month==month}
   choices=monthly[month]; choices.sort(key=lambda x:(x['state'] in used,-x['gust'],x['utc']))
   selected.append(choices.pop(0))
with (ROOT/'events_M.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['event_id','date_utc','verification_utc','station','lat','lon','gust_kt','state','location','source','source_url','narrative']);w.writeheader()
 for c in sorted(selected,key=lambda x:x['utc']):
  # nearest 12-hourly verification step; fixed 00/12 UTC starts for all leads.
  valid=c['utc'].replace(hour=0,minute=0,second=0)+dt.timedelta(hours=12*round((c['utc'].hour+c['utc'].minute/60)/12))
  w.writerow(dict(event_id=c['event_id'],date_utc=c['utc'].date(),verification_utc=valid.strftime('%Y-%m-%dT%H:%MZ'),station=c['station'],lat=c['lat'],lon=c['lon'],gust_kt=c['gust'],state=c['state'],location=c['location'],source=c['source'],source_url=c['source_url'],narrative=c['narrative']))
print('CANDIDATES',len(candidates),'DISTINCT_DAYS',len(byday),'SELECTED',len(selected),'MONTHS',dict(collections.Counter(c['utc'].month for c in selected)),'STATES',dict(collections.Counter(c['state'] for c in selected)),flush=True)
