"""Estimate actual eight-corner solid weight with audited STL mask alignment."""
from pathlib import Path
import json,struct,math
R=Path(__file__).resolve().parent
STL=R/'stage_C05/case/proj_temp/CaseE_PF.stl'
def sections(z):
 out=[]
 with STL.open('rb') as f:
  f.read(80);n=struct.unpack('<I',f.read(4))[0]
  for _ in range(n-12):
   d=f.read(50);t=struct.unpack_from('<9f',d,12);v=[t[i:i+3] for i in (0,3,6)];p=[]
   for i,j in ((0,1),(1,2),(2,0)):
    a,b=v[i],v[j]
    if a[2]<=z<b[2] or b[2]<=z<a[2]:
     w=(z-a[2])/(b[2]-a[2]);p.append((a[0]+w*(b[0]-a[0]),a[1]+w*(b[1]-a[1])))
   if len(p)==2 and math.dist(*p)>1e-5:out.append(tuple(p))
 return out
def inside(p,seg):
 x,y=p;cross=0
 for ((a,b),(c,d)) in seg:
  if (b<=y<d) or (d<=y<b):
   if a+(c-a)*(y-b)/(d-b)<x:cross^=1
 return cross==1
def nearest(p,seg):
 x,y=p;dmin=1e6
 for ((a,b),(c,d)) in seg:
  ux,uy=c-a,d-b;u=min(1,max(0,((x-a)*ux+(y-b)*uy)/(ux*ux+uy*uy)));dmin=min(dmin,math.hypot(x-a-u*ux,y-b-u*uy))
 return dmin
out={};targets=(50,51,52,54)
for tag,path in [('C1',R.parent/'resolution_crop_v2/C1v2_offset_samples.json'),('C05',R/'C05_offset_samples_a_r10.json')]:
 data=json.loads(path.read_text());dx=data['dx'];org=data['origin'];secs={z:sections(z) for z in (2.-dx/2,2.+dx/2)}
 rr={}
 for row in data['rows']:
  if row['id'] not in targets:continue
  x=row['xls_xy'][0]+250.50008+dx;y=row['xls_xy'][1]+250.60004+dx;z=2.;frac=[(v-o)/dx for v,o in zip((x,y,z),org)];ii=[math.floor(v) for v in frac];ww=[v-i for v,i in zip(frac,ii)];n=0;mass=0;corners=[]
  for c in range(8):
   grid=[ii[k]+((c>>k)&1) for k in range(3)];xyz=[org[k]+grid[k]*dx for k in range(3)];zp=xyz[2]-dx/2
   solid=inside((xyz[0]-dx/2,xyz[1]-dx/2),secs[zp]);weight=math.prod(ww[k] if c&(1<<k) else 1-ww[k] for k in range(3))
   n+=solid;mass+=weight*solid;corners.append({'xyz':xyz,'solid_proxy':solid,'weight':weight})
  rr[str(row['id'])]={'solid_corners_proxy':n,'solid_weight_proxy':mass,'extracted_fluid_corners':row['sample']['plus_dx']['fluid_corners'],'distance_2d_stl_m':nearest((x,y),sections(2.)),'distance_in_cells':nearest((x,y),sections(2.))/dx,'corners':corners}
 out[tag]=rr
(R/'solid_weights_proxy.json').write_text(json.dumps(out,indent=2)+'\n')
for tag,items in out.items():
 print(tag)
 for k,v in items.items():print(k,v['solid_corners_proxy'],v['extracted_fluid_corners'],round(v['solid_weight_proxy'],6),round(v['distance_2d_stl_m'],4),round(v['distance_in_cells'],4))
