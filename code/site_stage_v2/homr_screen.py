"""HOMR-only conservative pre-screen; run on Colab CPU; never pair ERA5 and stations."""
import csv,json,urllib.request,time,datetime as dt,traceback
from pathlib import Path
ROOT=Path('/content/site_stage_v2');ROOT.mkdir(exist_ok=True)
PLAINS='KMSP KBIS KABR KHON KSUX KLNK KGRI KLBF KTOP KMCI KDDC KOKC KTUL KRST KALO KDBQ KMLI KSGF KCOU KSTL KPIA KSPI'.split()
OTHER='KALB KCLE KDTW KPIT KORD KCMH KCVG KSDF KBNA KCRW KSYR KMDT KIAD KRDU KGSO KCLT KATL KBHM KMEM KLIT KSHV KJAN'.split()
T0='2007-10-01';T1='2022-03-31';OUT=ROOT/'homr_screen.csv'
def date(x):return x.get('date',{}).get('beginDate','')[:10]
def get(st):
 url=f'https://www.ncei.noaa.gov/access/homr/services/station/search?qid=ICAO%3A{st}&date=all&definitions=false'
 for n in range(4):
  try:
   r=json.load(urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'AI-Weather-Research/1.0'}),timeout=60));return r['stationCollection']['stations'],url
  except Exception:
   if n==3:raise
   time.sleep(3*(n+1))
def wind(st):
 stations,url=get(st)
 primary=[s for s in stations if any(i.get('idType')=='ICAO' and i.get('id')==st and i.get('date',{}).get('endDate')=='Present' for i in s.get('identifiers',[])) and any(e.get('element')=='WIND' and e.get('equipment',{}).get('equipment')=='ANEMSONIC' for e in s.get('elements',[]))]
 if len(primary)!=1:raise ValueError((st,'ambiguous primary ASOS HOMR records',len(primary),[s.get('ncdcStnId') for s in stations]))
 return primary[0],url
rows=[]
for group,sts in [('plains',PLAINS),('other',OTHER)]:
 for st in sts:
  try:
   s,url=wind(st);loc=s.get('location',{});els=s.get('elements',[])
   if st==PLAINS[0]:
    (ROOT/'schema_probe.json').write_text(json.dumps({'element_types':[(e.get('elementType'),list(e)) for e in els[:20]],'platforms':s.get('platforms',[])[:3]},indent=2))
   # HOMR wind records keyed by elementName WND and equipment, inspect raw per station
   eq=[]
   for e in els:
    if 'WIND' in json.dumps(e).upper() and ('ANEMSONIC' in json.dumps(e).upper() or 'ANEMCUP' in json.dumps(e).upper()):eq.append(e)
   reloc=[r for r in s.get('relocations',[]) if T0<=str(r.get('date',''))[:10]<=T1]
   la=loc.get('latitudes',[]);lo=loc.get('longitudes',[]);el=loc.get('elevations',[])
   geo=loc.get('geoInfo',{});counties=geo.get('counties',[]);states=geo.get('stateProvinces',[])
   row={'station':st,'region':group,'homr_id':s.get('ncdcStnId'),'county':counties[0].get('county') if counties else '', 'state':states[0].get('stateProvince') if states else '', 'lat':la[0].get('latitude_dec') if la else '', 'lon':lo[0].get('longitude_dec') if lo else '', 'elev_m':el[0].get('elevationMeters') if el else '', 'relocations_during':json.dumps(reloc),'wind_record_count':len(eq),'wind_records':json.dumps(eq),'source_url':url,'error':''}
  except Exception as ex:row={'station':st,'region':group,'error':repr(ex)}
  rows.append(row);print(st,row.get('error') or (row['wind_record_count'],len(json.loads(row['relocations_during']))),flush=True)
  with OUT.open('w',newline='') as f:
   wr=csv.DictWriter(f,fieldnames=['station','region','homr_id','county','state','lat','lon','elev_m','relocations_during','wind_record_count','wind_records','source_url','error']);wr.writeheader();wr.writerows(rows)
print('FINISHED',len(rows),flush=True)
