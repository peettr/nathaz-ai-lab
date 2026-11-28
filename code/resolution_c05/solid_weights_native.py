"""Exact native-flag weighted solid fraction for wall sampling corners."""
from pathlib import Path
import json,math,struct
R=Path(__file__).resolve().parent
out={}
for tag,path,mask in [('C1',R.parent/'resolution_crop_v2/C1v2_offset_samples.json',R.parent/'resolution_crop_v2/C1v2_flags_z0_90.bin'),('C05',R/'C05_offset_samples_a_r10.json',R/'C05_native_flags_z0_90.bin')]:
 d=json.loads(path.read_text());nx,ny=d['dimensions'][:2];dx=d['dx'];org=d['origin'];assert mask.stat().st_size==nx*ny*91
 flags=mask.read_bytes();rr={}
 for p in d['rows']:
  if p['id'] not in (50,51,52,54):continue
  x=p['xls_xy'][0]+250.50008+dx;y=p['xls_xy'][1]+250.60004+dx;z=2
  frac=[(v-o)/dx for v,o in zip((x,y,z),org)];ids=[math.floor(v) for v in frac];w=[v-i for v,i in zip(frac,ids)];weight=0.;solid=0;corners=[]
  for c in range(8):
   i=ids[0]+(c&1);j=ids[1]+((c>>1)&1);k=ids[2]+((c>>2)&1);f=flags[i+nx*(j+ny*k)];s=bool(f&1);wt=math.prod(w[h] if c&(1<<h) else 1-w[h] for h in range(3));weight+=wt*s;solid+=s;corners.append({'ijk':[i,j,k],'flag':f,'weight':wt,'solid':s})
  assert 8-solid==p['sample']['plus_dx']['fluid_corners'],(tag,p['id'],solid,p['sample']['plus_dx']['fluid_corners'])
  rr[str(p['id'])]={'solid_weight':weight,'solid_corners':solid,'flags_verified':True,'corners':corners,'physical_sampling_xyz':[x,y,z]}
 out[tag]=rr
(R/'solid_weights_native.json').write_text(json.dumps(out,indent=2)+'\n')
for tag,rr in out.items():
 print(tag,[(i,round(v['solid_weight'],7),v['solid_corners']) for i,v in rr.items()])
