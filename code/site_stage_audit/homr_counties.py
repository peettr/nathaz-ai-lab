import json,urllib.request,urllib.parse,time
from pathlib import Path
p=Path(__file__).resolve().parent/'homr_station_counties.json'
out=[]
for sid in 'MSP DSM OMA DTW PIT ALB DFW AUS FSD FAR ICT STL IND CLE BDL'.split():
 url='https://www.ncei.noaa.gov/access/homr/services/station/search?'+urllib.parse.urlencode({'qid':'ICAO:K'+sid,'date':'all','definitions':'false','phrData':'false'})
 a=json.load(urllib.request.urlopen(url,timeout=40))['stationCollection']['stations']
 for x in a:
  if not any(z.get('platform')=='ASOS' for z in x.get('platforms',[])):continue
  names=[z['name'] for z in x.get('names',[]) if z.get('nameType') in ('PRINCIPAL','PUB')]
  if sid=='AUS' and not any('BERGSTROM' in n.upper() for n in names):continue
  geo=x.get('location',{}).get('geoInfo',{})
  out.append({'station':'K'+sid,'ncdc_id':x['ncdcStnId'],'names':names,'counties':geo.get('counties',[]),'states':geo.get('stateProvinces',[]),'url':url})
 time.sleep(.1)
p.open('x').write(json.dumps(out,indent=2))
print(len(out))
