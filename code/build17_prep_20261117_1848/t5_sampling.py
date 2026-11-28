import math,itertools,json

def sampled(v,p):
 dx=v['spacing'][0]
 # Exact T2c/T2d B2u horizontal translation and real wall 2 m: wall plane 0.5 m, VTK z=2.5 m.
 xyz=(p['xls_xy'][0]+1010.50008-760+1.,p['xls_xy'][1]+1000.60004-750+1.,2.5)
 q=[(a-b)/dx for a,b in zip(xyz,v['origin'])];idx=[math.floor(a) for a in q];w=[a-i for a,i in zip(q,idx)]
 assert all(0<=i<n-1 for i,n in zip(idx,v['dims'])),(xyz,idx)
 su=solid=0.;corners=0
 for dz,dy,di in itertools.product((0,1),repeat=3):
  weight=(w[0] if di else 1-w[0])*(w[1] if dy else 1-w[1])*(w[2] if dz else 1-w[2]);k,j,i=idx[2]+dz,idx[1]+dy,idx[0]+di
  val=float(v['fields']['speed_mean'][k,j,i]);fluid=float(v['fields']['fluid'][k,j,i])>.5
  assert math.isfinite(val)
  su+=weight*val;solid+=weight*(not fluid);corners+=int(fluid)
 return {'Su':su,'Su_ratio':su/3.9286416,'xyz_m':xyz,'fluid_corners':corners,'solid_weight':solid}
def write_points(O,label,ref,v,vtk,sha):
 rows=[{'id':int(p['id']),'obs':float(p['after']),**sampled(v,p)} for p in ref['rows']]
 assert len({p['id'] for p in rows})==80 and all(math.isfinite(p['Su_ratio']) for p in rows)
 (O/f'{label}_points80.json').write_text(json.dumps({'label':label,'uref':ref['uref'],'rows':rows,'source_vtk_sha256':sha(vtk[0]),'sample_height_above_wall_m':2.0,'vtk_label_z_m':2.5},indent=2)+'\n')
 return O/f'{label}_points80.json'
