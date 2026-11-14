import json,requests,math
from pathlib import Path
p=Path(__file__).parent
# Grid coordinates generated from actual ACE2 Gaussian grid on Colab.
points=[('KMSP',45.37373733520508,266.5),('KDSM',41.384849548339844,266.5),('KOMA',41.384849548339844,264.5),('KORD',42.38207244873047,272.5),('KDTW',42.38207244873047,276.5),('KBUF',43.379295349121094,281.5),('KPIT',40.38762283325195,279.5),('KALB',42.38207244873047,286.5)]
features=[]
for state in ['MN','IA','NE','IL','MI','NY','PA','OH','WI','IN','NJ','CT','MA','VT','SD','KS']:
 r=requests.get(f'https://mesonet.agron.iastate.edu/geojson/network/{state}_ASOS.geojson',timeout=30);r.raise_for_status();features.extend(r.json()['features'])
def hav(a,b,c,d):
 a,b,c,d=map(math.radians,(a,b,c,d));x=math.sin((c-a)/2)**2+math.cos(a)*math.cos(c)*math.sin((d-b)/2)**2;return 6371*2*math.asin(math.sqrt(x))
rows=[]
for anchor,lat,lon in points:
 vals=[]
 for f in features:
  if not f.get('geometry') or not f['geometry'].get('coordinates'):continue
  lo,la=f['geometry']['coordinates'][:2]
  if not isinstance(la,(int,float)):continue
  vals.append((hav(lat,lon-360,la,lo),f['id'],f['properties'].get('sname'),f['properties'].get('state'),la,lo))
 vals.sort()
 rows.append({'anchor':anchor,'grid_lat':lat,'grid_lon':lon,'nearest_asos':vals[:3]})
print(json.dumps(rows,indent=2))
(p/'asos_nearest.json').write_text(json.dumps({'source':'https://mesonet.agron.iastate.edu/geojson/network/{STATE}_ASOS.geojson','searched_states':['MN','IA','NE','IL','MI','NY','PA','OH','WI','IN','NJ','CT','MA','VT','SD','KS'],'rows':rows},indent=2))
