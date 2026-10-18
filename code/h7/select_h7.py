#!/usr/bin/env python3
"""Pre-registered, score-blind DAT/date radar candidate ranking, read-only inputs."""
import ast,csv,json,math,collections,pathlib,datetime
P=pathlib.Path(__file__).resolve().parent; LAB=P.parents[1]
DAT=LAB/'loss_wind/dat_census_2019_2024_r2.json'; ST=LAB/'loss_wind/iem_station_census_r2.json'
source=(P.parent/'h6/.venv/lib/python3.10/site-packages/pyart/io/nexrad_common.py').read_text()
# Extract the static public radar coordinate dictionary without importing Py-ART.
root=ast.parse(source); loc={}
for n in root.body:
 if isinstance(n,ast.Assign):
  for t in n.targets:
   if isinstance(t,ast.Name) and t.id=='NEXRAD_LOCATIONS':loc=ast.literal_eval(n.value)
assert loc
rad={k:(v['lat'],v['lon'],v['elev']*.3048) for k,v in loc.items() if k.startswith('K') and v['elev']>0}
def km(a,b,c,d):
 la,lb=map(math.radians,(a,c));dl=math.radians(d-b);da=lb-la
 return 12742*math.asin(min(1,math.sqrt(math.sin(da/2)**2+math.cos(la)*math.cos(lb)*math.sin(dl/2)**2)))
stations=json.loads(ST.read_text())['stations']; groups=collections.defaultdict(list)
for p in json.loads(DAT.read_text())['features']:
 if p['efscale']!='TSTM/Wind':continue
 try: w=float(p['windspeed']);assert 0<w<200
 except:continue
 day=datetime.datetime.fromtimestamp(p['stormdate']/1000,datetime.timezone.utc).date().isoformat()
 near=sorted((km(p['lat'],p['lon'],la,lo),k,el) for k,(la,lo,el) in rad.items())[:2]
 dist,name,el=near[0]
 # radar refracted ray center above radar; ground height not available here, conservative radar-altitude proxy only
 h=dist*1000*math.sin(math.radians(.5))+(dist*1000)**2/(2*(4/3)*6371000)
 if dist<=25 and h<300:
  groups[(day,name)].append((p,dist,h,near))
rows=[]
for (day,name),points in groups.items():
 la,lo,_=rad[name]
 nearst=[s for s in stations if km(s['lat'],s['lon'],la,lo)<=60 and (not s.get('begin') or s['begin']<=day) and (not s.get('end') or s['end']>=day)]
 if len(points)>=8: rows.append({'day':day,'radar':name,'n_dat_near':len(points),'n_stations_metadata_60km':len(nearst),'max_proxy_height_m':round(max(x[2] for x in points),1),'second_radar_km_median':round(sorted(x[3][1][0] for x in points)[len(points)//2],1),'sample_ids':','.join(str(x[0]['objectid']) for x in points[:3])})
rows.sort(key=lambda r:(-r['n_dat_near'],r['day']))
with (P/'candidate_screen_h7.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps(rows[:25],indent=2))
