#!/usr/bin/env python3.10
"""Host-side independent reduction of verified T8 slice and frozen AIJ profile."""
import hashlib,json,math,pathlib,sys
import numpy as np
R=pathlib.Path(__file__).resolve().parent;E=R/'evidence'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 points=E/'points80.json';sl=E/'upstream_slice.npz'
 for p in (points,sl):assert p.is_file() and sha(p)==(E/(p.name+'.sha256')).read_text().strip(),p
 baseline='6b57372b53206a9af04069bf25c0f756f77e78ef92d86d658a1495c863f4b279'
 assert sha(points)==baseline,'determinism gate failed; no physical verdict'
 obs=json.loads((R/'comparison.json').read_text());rows=[]
 with np.load(sl) as data:
  u=data['u_avg'];k=data['tke'];fluid=data['fluid'];meta=json.loads(str(data['metadata']))
  assert u.shape==(62,201,61,3) and k.shape==fluid.shape==(62,201,61)
  assert meta['origin']==[0.,0.,-20.] and meta['numerical_wall_z_m']==0.5
  for x in (5,30,45):
   for o in obs['rows']:
    z=float(o['z_m']);index=z+0.5;lo=math.floor(index);w=index-lo
    good=(fluid[lo,:,x]>.5)&(fluid[lo+1,:,x]>.5)
    n=int(good.sum());assert n
    km=float(np.mean(((1-w)*k[lo,:,x].astype('f8')+w*k[lo+1,:,x].astype('f8'))[good]))
    um=float(np.mean(((1-w)*u[lo,:,x,0].astype('f8')+w*u[lo+1,:,x,0].astype('f8'))[good]))
    rows.append(dict(x_m=x,z_agl_m=z,fluid_columns=n,total_columns=201,kappa=km/float(o['k_obs_m2s2']),U_over_Uobs=um/float(o['U_obs_mps'])))
  near=fluid[2:4,:,45];support=(near>.5).all(axis=0);nearest=[]
  for j in range(201):
   h=np.flatnonzero((fluid[2:4,j,46:61]<=.5).any(axis=0));nearest.append(int(h[0]+46) if len(h) else None)
  geo={'x45_2m_fluid_count':int(support.sum()),'total':201,'each_support_fluid_count':[int((near[i]>.5).sum()) for i in range(2)],'nearest_solid_downwind_x_by_y':nearest,'min_distance_m':min((a-45 for a in nearest if a is not None),default=None),'max_visible_distance_m':max((a-45 for a in nearest if a is not None),default=None),'y_without_solid_in_slice':sum(a is None for a in nearest),'interpretation_limit':'first solid in x=46..60 m at either 2m interpolation support; does not establish full 3D building distance'}
 gate=[r['kappa'] for r in rows if r['x_m']==45 and r['z_agl_m'] in (2.,5.,10.,15.9)]
 assert len(gate)==4
 verdict='明显衰减' if sum(a<0.7 for a in gate)>=3 else '基本保持' if all(0.8<=a<=1.25 for a in gate) else '中间（不判）'
 out={'points80_sha256':sha(points),'slice_sha256':sha(sl),'gate_x45_kappa':gate,'verdict':verdict,'profile':rows,'geometry':geo}
 (R/'T8_verdict.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 print('GATE',verdict,'points80',sha(points),'slice',sha(sl))
 for a in rows:print(f"x={a['x_m']:2} z={a['z_agl_m']:4g} fluid={a['fluid_columns']:3}/201 kappa={a['kappa']:.6f} U/Uobs={a['U_over_Uobs']:.6f}")
 print('GEOMETRY',json.dumps({k:v for k,v in geo.items() if k!='nearest_solid_downwind_x_by_y'},ensure_ascii=False))
if __name__=='__main__':main()
