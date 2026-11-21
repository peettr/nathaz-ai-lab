#!/usr/bin/env python3.10
"""Compare native full-height flags, source-derived mirror support, N_far coverage."""
import pathlib,json,numpy as np,hashlib
R=pathlib.Path(__file__).resolve().parent
D=R/'build2_analysis';D.mkdir(exist_ok=False)
attempts=[p for p in R.glob('build2_attempt_*/evidence') if (p/'on_city_flags.npz').is_file() and (p/'off_city_flags.npz').is_file()]
assert len(attempts)==1,attempts
EV=attempts[0]
A=np.load(EV/'on_city_flags.npz')['flags']
B=np.load(EV/'off_city_flags.npz')['flags']
assert A.shape==B.shape==(270,500,500)
wrong=int(np.count_nonzero(A!=B));solid=(A&3)==1
fluid=(A&3)!=1
# Eligible cell predicate matches facade_eligible in the actually staged kernel.
ns=np.zeros(A.shape,dtype=np.uint8)
for axis,delta in ((2,1),(2,-1),(1,1),(1,-1)):
 n=np.roll(solid,-delta,axis=axis);ns+=n.astype(np.uint8)
zsolid=np.roll(solid,-1,axis=0)|np.roll(solid,1,axis=0)
elig=fluid&(ns==1)&~zsolid
elig[:2]=False;elig[-2:]=False;elig[:,:2]=False;elig[:,-2:]=False;elig[:,:,:2]=False;elig[:,:,-2:]=False
multi=fluid&(ns>=2);ground=fluid&(ns>=1)&zsolid
# For each +x/-x/+y/-y face, test a tangential neighbour in 4 directions.
mirror=np.zeros(A.shape,dtype=bool);link_count=0
for axis,sgn in ((2,1),(2,-1),(1,1),(1,-1)):
 normal=np.roll(solid,-sgn,axis=axis)
 face=elig&normal
 for tangent_axis in (0,1,2):
  if tangent_axis==axis:continue
  for tang in (-1,1):
   # partner = n - tangential step; upstream = n + normal - tangent.
   partner=np.roll(elig,tang,axis=tangent_axis)
   partner_normal=np.roll(normal,tang,axis=tangent_axis)
   upstream=np.roll(np.roll(solid,tang,axis=tangent_axis),-sgn,axis=axis)
   valid=face&partner&partner_normal&upstream
   mirror|=valid;link_count+=int(np.count_nonzero(valid))
mirror[:2]=False;mirror[-2:]=False;mirror[:,:2]=False;mirror[:,-2:]=False;mirror[:,:,:2]=False;mirror[:,:,-2:]=False
r={'shape_zyx':list(A.shape),'flag_mismatch_cells':wrong,'flag_equal':wrong==0,'multiple_horizontal_normals_native_bounce':int(np.count_nonzero(multi)),'facade_and_vertical_solid_native_bounce':int(np.count_nonzero(ground)),'single_horizontal_eligible_cells':int(np.count_nonzero(elig)),'mirror_cells_with_at_least_one_active_diagonal_link':int(np.count_nonzero(mirror)),'mirror_diagonal_links':link_count,'rule':'native flags; links require n and tangential partner eligible, and solid upstream; ambiguous horizontal/vertical neighbours bounce'}
ref=json.loads((R/'build2_stage/B2u_reference_points.json').read_text());ids={31,39,40,47,48,49,65,66,69,77,79}; rows=[]
for p in ref['rows']:
 if int(p['id']) not in ids:continue
 x=float(p['xls_xy'][0])+251.50008;y=float(p['xls_xy'][1])+251.60004
 ix0=max(2,int(np.floor(x-10)));ix1=min(498,int(np.ceil(x+10))+1)
 iy0=max(2,int(np.floor(y-10)));iy1=min(498,int(np.ceil(y+10))+1)
 yy,xx=np.ogrid[iy0:iy1,ix0:ix1];ball=(xx-x)**2+(yy-y)**2<=100
 # Wall plane is 0.5 m, so label z=1..5 is 0.5..4.5 m above it.
 adjacent=(fluid&(ns>=1))[21:26,iy0:iy1,ix0:ix1]&ball[None]
 selected=mirror[21:26,iy0:iy1,ix0:ix1]&ball[None]
 denom=int(adjacent.sum());num=int(selected.sum());assert denom>=num
 rows.append({'id':int(p['id']),'center_xy_m':[x,y],'wall_adjacent_cells':denom,'mirror_cells':num,'f_i':num/denom if denom else None})
assert {x['id'] for x in rows}==ids
r['N_far']=sorted(rows,key=lambda v:v['id']);r['f_bar']=sum(x['f_i'] for x in rows)/len(rows) if all(x['f_i'] is not None for x in rows) else None
(D/'native_flag_coverage.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps({k:v for k,v in r.items() if k!='N_far'},indent=2))
print('N_far',r['N_far'])
