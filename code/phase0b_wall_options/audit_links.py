"""Count voxel fluid/solid directed D3Q19 links; this is not STL ray q."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'phase0_geometry'))
from ibm_geometry import clean_mesh, read_case_e, voxel_proxy
s, odd=voxel_proxy(clean_mesh(read_case_e())[0]); assert odd==0
# Include only pairs fully inside proxy bounds, not ground and open outer boundaries.
results={}
for dx in (-1,0,1):
 for dy in (-1,0,1):
  for dz in (-1,0,1):
   if abs(dx)+abs(dy)+abs(dz) not in (1,2):continue
   offsets=(dz,dy,dx)
   a=[];b=[]
   for n,d in zip(s.shape,offsets):
    if d>=0:a.append(slice(0,n-d));b.append(slice(d,n))
    else:a.append(slice(-d,n));b.append(slice(0,n+d))
   start=s[tuple(a)];end=s[tuple(b)]
   results[str((dx,dy,dz))]=int((~start & end).sum())
count=sum(results.values());out={'directed_fluid_to_solid_D3Q19_links_proxy':count,'q_float32_bytes':4*count,'q_float16_bytes':2*count,'distribution':'not wall intersection count; ray-STL q and link attribution remain uncomputed','per_direction':results}
Path('link_proxy.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
