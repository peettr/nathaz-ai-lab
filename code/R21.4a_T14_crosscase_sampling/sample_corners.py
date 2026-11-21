#!/usr/bin/env python3
"""Read-only B2u VTK corner sampler; exact T2c coordinates, T12b header layout."""
import argparse,hashlib,itertools,json,math,pathlib,struct
from sample_vtk_t12 import header,SOURCE
ap=argparse.ArgumentParser();ap.add_argument('--vtk',default=SOURCE);ap.add_argument('--points',default='B2u_reference_points.json');ap.add_argument('--out',default='B2u_corners_z2p5.json');args=ap.parse_args()
p=pathlib.Path(args.vtk);assert p.is_file(),p
points=json.loads(pathlib.Path(args.points).read_text())['rows'];assert len(points)==80
D,origin,spacing,offsets=header(p);assert D==(500,500,270) and origin==(0.,0.,-20.) and spacing==(1.,1.,1.)
rows=[]
with p.open('rb') as f:
 for r in points:
  xyz=[r['xls_xy'][0]+1010.50008-760+1.,r['xls_xy'][1]+1000.60004-750+1.,2.5]
  ijk=[math.floor((a-b)/step) for a,b,step in zip(xyz,origin,spacing)];frac=[(a-b)/step-i for a,b,step,i in zip(xyz,origin,spacing,ijk)]
  assert all(0<=i<n-1 for i,n in zip(ijk,D));cs=[]
  for dk,dj,di in itertools.product((0,1),repeat=3):
   i,j,k=ijk[0]+di,ijk[1]+dj,ijk[2]+dk;wt=math.prod(frac[t] if q else 1-frac[t] for t,q in enumerate((di,dj,dk)));cell=(k*D[1]+j)*D[0]+i
   f.seek(offsets['fluid']+4*cell);fluid=struct.unpack('>f',f.read(4))[0]
   f.seek(offsets['speed_mean']+4*cell);speed=struct.unpack('>f',f.read(4))[0]
   assert math.isfinite(fluid) and math.isfinite(speed)
   cs.append({'ijk':[i,j,k],'weight':wt,'fluid':fluid,'speed_mean_mps':speed})
  old=sum(c['weight']*c['speed_mean_mps'] for c in cs)
  valid=[c for c in cs if c['fluid']>.5];w=sum(c['weight'] for c in valid)
  if len(valid)>=4 and w>0: new=sum(c['weight']*c['speed_mean_mps'] for c in valid)/w;rule='fluid_renormalized'
  else:
   assert valid,'no fluid corner';near=min(valid,key=lambda c:(sum(((c['ijk'][t]-((xyz[t]-origin[t])/spacing[t]))*spacing[t])**2 for t in range(3)),tuple(c['ijk'])));new=near['speed_mean_mps'];rule='nearest_fluid_corner'
  rows.append({'id':int(r['id']),'xyz_m':xyz,'corners':cs,'old_speed_mean_mps':old,'new_speed_mean_mps':new,'rule':rule,'fluid_corners':len(valid)})
result={'source_vtk':str(p),'source_bytes':p.stat().st_size,'dimensions':D,'origin':origin,'spacing':spacing,'label_z_m':2.5,'rows':rows}
out=pathlib.Path(args.out);out.write_text(json.dumps(result,indent=2)+'\n');h=hashlib.sha256(out.read_bytes()).hexdigest();out.with_name(out.name+'.sha256').write_text(h+'  '+out.name+'\n');print('sampled',len(rows),'sha256',h,'max_delta',max(abs(x['new_speed_mean_mps']-x['old_speed_mean_mps']) for x in rows),flush=True)
