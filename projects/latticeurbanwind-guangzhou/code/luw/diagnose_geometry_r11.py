"""Read-only geometry diagnostic of Case E, independent of new solver runs."""
from pathlib import Path
import csv, json, math
import numpy as np
from scipy.ndimage import distance_transform_edt
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
R=Path(__file__).parent
S=R/'han2026_supp/LatticeUrbanWind_repo/examples/example_ProfileResearch_noDEM/proj_temp/CaseE_PF.stl'
D=np.dtype([('normal','<f4',(3,)),('v','<f4',(3,3)),('attr','<u2')])
a=np.fromfile(S,dtype=D,offset=84); assert len(a)==9210
# Strip the last 12 base triangles (prior runs established this split).
v=a['v'][:-12].astype(float)
# PF to cropped local coordinates; xls raw point to local PF via previously fitted translation.
SHIFT=np.array([1010.50008-760,1000.60004-750]); v[:,:,:2]-=np.array([760,750])
points={int(row['id']):row for row in csv.DictReader((R/'CaseE_W_points_full_r7.csv').open())}
# z=2 m horizontal section, half-open edge convention of earlier VTK mask extraction.
def section(z):
 seg={}
 for t in v:
  p=[]
  for i,j in ((0,1),(1,2),(2,0)):
   za,zb=t[i,2],t[j,2]
   if (za<=z<zb) or (zb<=z<za):
    w=(z-za)/(zb-za); p.append(t[i,:2]+w*(t[j,:2]-t[i,:2]))
  if len(p)==2 and np.linalg.norm(p[0]-p[1])>1e-5:
   key=tuple(sorted(tuple(np.round(q,4)) for q in p));seg[key]=p
 return np.array(list(seg.values()))
seg=section(2.0)
# All plane nodes at integral x,y. VTK solid occupancy is the raw STL interior at (node_x-1,node_y-1),
# consistent with prior z=2/10m zero-speed comparison (IoU 0.9999/1.0). No re-run or claimed direct flag dump.
grid=np.arange(0,500,dtype=float)
def mask_at(xs,ys):
 result=np.zeros((len(ys),len(xs)),bool)
 for j,y in enumerate(ys):
  hit=[]
  for (x0,y0),(x1,y1) in seg:
   if (y0<=y<y1) or (y1<=y<y0):hit.append(x0+(x1-x0)*(y-y0)/(y1-y0))
  hit=np.sort(hit);assert len(hit)%2==0,(y,len(hit))
  result[j]=np.searchsorted(hit,xs,side='left')%2==1
 return result
solid_raw=mask_at(grid,grid);solid_vox=mask_at(grid-1,grid-1)
# Segment distance for STL walls, excluding triangles at distant elevations.
def dseg(xy):
 aa=seg[:,0]; d=seg[:,1]-aa; q=xy-aa
 w=np.clip(np.einsum('ij,ij->i',q,d)/np.maximum(np.einsum('ij,ij->i',d,d),1e-20),0,1)
 return float(np.linalg.norm(q-w[:,None]*d,axis=1).min())
vox_d=distance_transform_edt(~solid_vox)
# Gap width along cross-wind y at fixed x. Missing second flank within +/-30m is not a resolved street canyon.
def gap(mask,x,y):
 i=int(round(x));j=int(round(y))
 if not (0<=i<500 and 0<=j<500) or mask[j,i]:return 0.
 lo=j;hi=j
 while lo>0 and not mask[lo-1,i]:lo-=1
 while hi<499 and not mask[hi+1,i]:hi+=1
 return float(hi-lo+1) if lo>0 and hi<499 else float('nan')
# Continuous STL gap at fixed x using vertical-section intersections; only nearest two walls delimiting fluid.
def gap_stl(x,y):
 crossing=[]
 for (x0,y0),(x1,y1) in seg:
  if (x0<=x<x1) or (x1<=x<x0):crossing.append(y0+(y1-y0)*(x-x0)/(x1-x0))
 crossing.sort()
 k=np.searchsorted(crossing,y,'left')
 if k%2: return 0.
 if k==0 or k==len(crossing):return float('nan')
 return float(crossing[k]-crossing[k-1])
# Trilinear sampling of physical point x+1,y+1,z=2: x/y fractional, z=2 exactly lattice node.
def corners(x,y):
 u=x+1;w=y+1;i=math.floor(u);j=math.floor(w)
 return int(sum(not solid_vox[q,p] for q in (j,j+1) for p in (i,i+1)))
# Geometrically choose control points: after scalar residual below 0.04, >=8 fluid corners, distribute spatially.
issues=[50,51,52,54,23,25,37,17]
def coord(i):
 r=points[i];return np.array([float(r['x']),float(r['y'])])+SHIFT
controls=[i for i,r in points.items() if i not in issues and abs(float(r['s_exp_shift'])-float(r['after']))<.04 and int(r['fluid_shift'])==8]
# sample controls across quadrants and range of STL wall distances (deterministic greedy)
controls=sorted(controls,key=lambda i:(-dseg(coord(i)),i))
chosen=[]
for i in controls:
 if all(np.linalg.norm(coord(i)-coord(k))>45 for k in chosen):chosen.append(i)
 if len(chosen)==4:break
assert len(chosen)==4,chosen
rows=[]
for role,ids in [('persistent',issues),('control',chosen)]:
 for idx in ids:
  r=points[idx];xy=coord(idx);x,y=xy; sx,sy=x+1,y+1
  # Width at the point; look west 30m along y near the measurement's lateral position.
  transect=[]
  for xp in range(max(1,int(math.floor(x-30))),int(math.floor(x))+1):
   a=gap_stl(xp,y);b=gap(solid_vox,xp+1,y+1)
   if np.isfinite(a) and a>0 and np.isfinite(b):transect.append((xp,a,b))
  closures=[item for item in transect if item[2]==0 or item[2]<=.5*item[1]]
  stld=dseg(xy);vd=float(vox_d[int(round(sy)),int(round(sx))])
  rows.append(dict(id=idx,role=role,xls_x=float(r['x']),xls_y=float(r['y']),after=float(r['after']),s_exp_r7=float(r['s_exp_shift']),residual=float(r['s_exp_shift'])-float(r['after']),stl_wall_m=stld,voxel_wall_center_m=vd,stl_crosswind_gap_m=gap_stl(x,y),voxel_crosswind_gap_m=gap(solid_vox,sx,sy),upstream_30m_compared_n=len(transect),upstream_30m_halved_or_closed_n=len(closures),upstream_30m_halved_or_closed=bool(closures),upstream_example_x_m=','.join(str(t[0]) for t in closures[:8]),fluid_xy_corners_z2=corners(x,y),r7_fluid_3d_corners=int(r['fluid_shift'])))
  fig,ax=plt.subplots(figsize=(6.5,6.2))
  ax.imshow(solid_vox,origin='lower',extent=(-.5,499.5,-.5,499.5),cmap='Greys',alpha=.65,interpolation='nearest',vmin=0,vmax=1)
  ax.add_collection(LineCollection(seg,colors='#198e98',linewidths=.5,alpha=.8,label='STL section z=2m'))
  ax.plot(x,y,'o',color='crimson' if role=='persistent' else '#2453df',markersize=9,label=f'point {idx}: WT at raw XY')
  ax.plot(sx,sy,'+',color='#ff9800',markersize=9,label='VTK sample (+1,+1,0)m')
  ax.annotate('',xy=(x-16,y+23),xytext=(x-28,y+23),arrowprops=dict(arrowstyle='->',color='royalblue',lw=2));ax.text(x-28,y+25,'W wind',fontsize=8)
  ax.set_xlim(x-30,x+30);ax.set_ylim(y-30,y+30);ax.set_aspect('equal');ax.grid(alpha=.12)
  ax.set(xlabel='cropped PF x (m)',ylabel='cropped PF y (m)',title=f'Case E #{idx} ({role}): STL outline vs LUW solid nodes')
  ax.legend(loc='lower center',bbox_to_anchor=(.5,-.26),ncol=2,fontsize=7)
  fig.savefig(R/f'CaseE_local_{idx}_r11v2.png',dpi=160,bbox_inches='tight');plt.close(fig)
with (R/'CaseE_geometry_table_r11v2.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
summary={'source_stl':str(S),'triangles_building':len(v),'section_segments':len(seg),'point_registration':'assumption xls raw XY identity; PF=raw+(1010.50008,1000.60004,-0.10); VTK solid offset(+1,+1,0)m','controls':chosen,'rows':rows,'definitions':{'wall_stl':'minimum Euclidean distance from raw XY point to deduplicated z=2m STL section edges','wall_voxel':'distance transform from nearest solid lattice node center to VTK sample (+1,+1)m in cropped PF frame, rounded to nearest node; not surface distance','crosswind_gap':'y-direction wall-to-wall distance at point x for STL and count of contiguous 1m fluid lattice nodes for voxel; NaN when unbounded within domain','upstream':'at 1m x increments 30m west; compare crosswind gaps at fixed point y; failure if voxel zero or <= half STL; only where STL has two enclosing walls','fluid_corners':'xy 4 corners at exact z=2m; prior R7 3D-corner count included z=2 and z=3'}}
(R/'CaseE_geometry_r11v2.json').write_text(json.dumps(summary,indent=2,allow_nan=False))
print('controls',chosen,'segments',len(seg))
for row in rows:print(row['id'],row['role'],'wall',round(row['stl_wall_m'],2),round(row['voxel_wall_center_m'],2),'gap',round(row['stl_crosswind_gap_m'],2),round(row['voxel_crosswind_gap_m'],2),'halved',row['upstream_30m_halved_or_closed'],'fluid',row['fluid_xy_corners_z2'],row['r7_fluid_3d_corners'])
