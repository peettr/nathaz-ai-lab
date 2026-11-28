"""Read-only HOMR audit: preserve dated wind-element and coordinate provenance, no inference of model."""
import csv,json,urllib.request,urllib.parse,time
from pathlib import Path
root=Path(__file__).resolve().parent
sids='MSP DSM OMA DTW PIT ALB DFW AUS FSD FAR ICT STL IND CLE BDL'.split()
rows=[];errors=[]
for sid in sids:
 url='https://www.ncei.noaa.gov/access/homr/services/station/search?'+urllib.parse.urlencode({'qid':'ICAO:K'+sid,'date':'all','definitions':'false'})
 try:
  stations=json.load(urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'PETW-AIWeather-site-audit/1.0'}),timeout=60))['stationCollection']['stations']
  candidates=[s for s in stations if any(p.get('platform')=='ASOS' for p in s.get('platforms',[]))]
  for s in candidates:
   loc=s.get('location',{});pairs=[p for p in loc.get('latLonPairs',[]) if p.get('date',{}).get('beginDate','')[:4]>='2000']
   winds=[x for x in s.get('elements',[]) if x.get('element')=='WIND']
   rows.append({'station':'K'+sid,'ncdc_id':s['ncdcStnId'],'api_url':url,'wind_elements':json.dumps(winds,ensure_ascii=False),'locations_2000_plus':json.dumps(pairs,ensure_ascii=False),'relocations':json.dumps(s.get('relocations',[]),ensure_ascii=False),'updates_wind':[x for x in s.get('updates',[]) if 'WIND' in x.get('description','').upper() or 'ASOS' in x.get('description','').upper()]})
  print(sid,'candidates',len(candidates),'wind_elements',[len([x for x in s.get('elements',[]) if x.get('element')=='WIND']) for s in candidates],flush=True)
 except Exception as e:errors.append({'station':'K'+sid,'error':repr(e),'url':url});print(sid,repr(e),flush=True)
 time.sleep(.2)
with (root/'homr_history.json').open('w') as f:json.dump({'rows':rows,'errors':errors},f,ensure_ascii=False,indent=2)
