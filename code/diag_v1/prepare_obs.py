"""Join HURDAT2 2026 edition to EBTRK v3.0.2 by NHC storm ID and UTC date."""
import csv,math,pathlib,collections,json
import numpy as np
P=pathlib.Path(__file__).resolve().parent
BASE=P.parent
sites=list(csv.DictReader(open(BASE/'sites.csv')))
slat=np.array([float(r['lat']) for r in sites]);slon=np.array([float(r['lon']) for r in sites])
def dist(lat,lon):
 a=np.radians(lat-slat);b=np.radians(lon-slon)
 q=np.sin(a/2)**2+np.cos(np.radians(lat))*np.cos(np.radians(slat))*np.sin(b/2)**2
 return 12742*np.arcsin(np.sqrt(np.clip(q,0,1)))
eb={}
for line in open(P/'EBTRK_AL_1851_2021.txt'):
 t=line.split()
 if len(t)<18:continue
 try:
  year=int(t[3]);key=(t[0],f'{year:04d}{t[2]}')
  if 1988<=year<=2018:eb[key]=(float(t[8]),float(t[-2]),t[-3],t[-1])
 except (ValueError,IndexError):pass
rows=[];all_tropical=0;matched=0
for line in open(BASE/'hurdat2-1851-2025-092326.txt'):
 t=[v.strip() for v in line.split(',')]
 if t[0].startswith('AL') and t[0][2:4].isdigit() and len(t[0])==8:
  storm=t[0];continue
 if len(t)<8:continue
 try:
  y=int(t[0][:4]);status=t[3];la=float(t[4][:-1])*(1 if t[4][-1]=='N' else -1);lo=float(t[5][:-1])*(-1 if t[5][-1]=='W' else 1);v=int(t[6]);pc=int(t[7])
 except (ValueError,IndexError):continue
 if not(1988<=y<=2018 and status in ('TS','HU') and v>=35):continue
 all_tropical+=1
 dd=dist(la,lo)
 if dd.min()>500:continue
 e=eb.get((storm,t[0]+t[1][:2]));matched+=bool(e)
 row=dict(storm=storm,date=t[0]+t[1],lat=la,lon=lo,vmax=v,pc=pc if pc>0 else '',rmw=e[0] if e and e[0]>0 else '',land_km=e[1] if e and e[1]>-9000 else '',eb_type=e[2] if e else '',eb_source=e[3] if e else '',d_site_km=round(float(dd.min()),3))
 rows.append(row)
with open(P/'obs_inputs.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps(dict(all_tropical=all_tropical,near_points=len(rows),matched_eb=matched,pc_valid=sum(r['pc']!='' for r in rows),rmw_valid=sum(r['rmw']!='' for r in rows),example=rows[0]),indent=2))
