"""Read-only offline native-flag/STL audit of Case E B2u probes. Run python3.10."""
from pathlib import Path
import csv, json, sys
import numpy as np
from scipy import ndimage
from scipy.stats import spearmanr
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
R=Path(__file__).resolve().parent; L=R.parents[1]
raw=list(csv.DictReader((L/'method_study/B2u_scalar_mean/points_80.csv').open()))
feat={int(r['id']):r for r in csv.DictReader((L/'method_study/split_diag/points_80.csv').open())}
assert len(raw)==80 and set(int(r['id']) for r in raw)==set(feat)==set(range(1,81))
a=np.load(L/'wp1b_ibm/phaseC2_caseE_prep/step4_flags_z0_90.npz')['flags']
b=np.load(L/'wp1_nearwall/city_stab/ma010_flags_z0_62.npz');b=b[b.files[0]]
assert a.shape==(91,500,500) and np.array_equal(a[:63],b)
solid=(a&1)!=0
sys.path.insert(0,str(L/'wp1b_ibm/phase0_geometry'))
from ibm_geometry import read_case_e, clean_mesh, section_segments
tri,_=clean_mesh(read_case_e()); seg=section_segments(tri,2.)
assert len(seg)>0
# Native voxel origin is shifted (+1,+1) grid indexes; physical STL/observations are unshifted.
result=[]; detailed={}
for rr in raw:
 i=int(rr['id']); f=feat[i]; obs=float(rr['obs']); su=float(rr['Su']); rat=su/obs
 cls='fast' if rat>1.2 else 'slow' if rat<.8 else 'near'
 def num(s):return float(s) if s not in ('','None','nan') else None
 rec={'id':i,'class_Su':cls,'Su_obs':rat,'Su':su,'obs_W':obs,'S_obs':float(rr['S'])/obs,'Sstar_obs':float(rr['Sstar'])/obs,
      'x_m':float(f['x']),'y_m':float(f['y']),'wall_m':num(f['wall_m']),'width_x_m':num(f['width_x_m']),'width_y_m':num(f['width_y_m']),
      'width_min_m':num(f['width_min_m']),'disk50_cover':num(f['disk50_building_plan_fraction']),'upwind_solid_frac':num(f['upwind_11m_strip_solid_50m']),
      'upstream_nearest_solid_m':num(f['upstream_nearest_solid_m']),'reverse_ux_proxy':str(f['reverse_ux_proxy'])=='True',
      'k_m2s2':float(rr['k']),'solid_corners':int(rr['solid_corners'])}
 result.append(rec)
 if i not in (50,74): continue
 x,y=rec['x_m'],rec['y_m'];ix=int(round(x+1));iy=int(round(y+1));
 # 8 trilinear corners at fixed physical sampling location, inspect z=22 (AGL 2m).
 ix0=int(np.floor(x+1));iy0=int(np.floor(y+1)); z=22
 corners=[{'x':xx,'y':yy,'solid':bool(solid[z,yy,xx]),'weight_xy':float((1-abs(xx-(x+1)))*(1-abs(yy-(y+1))))} for yy in (iy0,iy0+1) for xx in (ix0,ix0+1)]
 layers=[]
 for h in (1,2,3,4,5,10):
  zz=20+h; ss=solid[zz];xx0=max(0,ix-15);xx1=min(500,ix+16);yy0=max(0,iy-15);yy1=min(500,iy+16)
  loc=~ss[yy0:yy1,xx0:xx1]
  # local 31x31 fluid connectivity to the upwind (west) edge, not a whole-domain flow path.
  lab,nlab=ndimage.label(loc,structure=ndimage.generate_binary_structure(2,1)); labid=int(lab[iy-yy0,ix-xx0]);edge=bool(labid and (lab[:,0]==labid).any())
  # contiguous fluid center run containing the probe along two axes
  def width(vec,center):
   if not vec[center]:return 0
   left=center; right=center
   while left>0 and vec[left-1]:left-=1
   while right+1<len(vec) and vec[right+1]:right+=1
   return right-left+1
  nx=width(loc[iy-yy0,:],ix-xx0);ny=width(loc[:,ix-xx0],iy-yy0)
  layers.append({'AGL_m':h,'native_z':zz,'probe_native_solid':bool(ss[iy,ix]),'fluid_in_31x31':int(loc.sum()),'fluid_component_size_in_31x31':int((lab==labid).sum()) if labid else 0,
                 'connected_to_local_west_edge':edge,'x_fluid_run_cells':nx,'y_fluid_run_cells':ny,'solid_in_31x31':int((~loc).sum())})
 # Entire z=22 plane inlet connectivity (6-neighbour 2D analog) and 3D 1-10m region's component at probe.
 sl=~solid[22]; label,n=ndimage.label(sl,structure=ndimage.generate_binary_structure(2,1));id2=int(label[iy,ix]);
 # 3-D flood is bounded to z=21..30 only and should not be represented as full 3-D connectivity.
 cube=~solid[21:31];lab3,n3=ndimage.label(cube,structure=ndimage.generate_binary_structure(3,1));id3=int(lab3[1,iy,ix]);
 # STL section nearest wall and opposite-wall candidates sourced from existing audit proxy.
 d=np.asarray(seg[:,1]-seg[:,0]);v=np.asarray(seg[:,0]);q=np.array([x,y]);t=np.clip(((q-v)*d).sum(1)/np.maximum((d*d).sum(1),1e-12),0,1);dist=np.linalg.norm(v+t[:,None]*d-q,axis=1)
 details={'id':i,'physical_xy_m':[x,y],'native_xy_nearest':[ix,iy],'STL_nearest_wall_m':float(dist.min()),'STL_width_x_m':rec['width_x_m'],'STL_width_y_m':rec['width_y_m'],
          'trilinear_xy_corners':corners,'layers':layers,
          'at_z2_global_2d_inlet_connected':bool(id2 and (label[:,0]==id2).any()),'at_z2_2d_component_cells':int((label==id2).sum()) if id2 else 0,
          'z1_to10_3d_inlet_connected':bool(id3 and (lab3[:,:,0]==id3).any()),'z1_to10_3d_component_cells':int((lab3==id3).sum()) if id3 else 0}
 detailed[i]=details
 # Two inspectable local maps, same physical alignment, native z=22 and STL z=2m.
 fig,ax=plt.subplots(figsize=(6,6));x0=max(0,ix-15);x1=min(500,ix+16);y0=max(0,iy-15);y1=min(500,iy+16)
 ax.imshow(solid[22,y0:y1,x0:x1],origin='lower',extent=(x0-1.5,x1-1.5,y0-1.5,y1-1.5),cmap='gray_r',vmin=0,vmax=1,interpolation='nearest')
 near=((seg[:,:,0]>=x-17)&(seg[:,:,0]<=x+17)&(seg[:,:,1]>=y-17)&(seg[:,:,1]<=y+17)).any(axis=1)
 ax.add_collection(LineCollection(seg[near],colors='red',linewidths=.8,label='STL z=2 m'))
 ax.scatter([x],[y],marker='x',c='cyan',s=80,zorder=4)
 ax.set(xlim=(x-15,x+15),ylim=(y-15,y+15),xlabel='physical x m (+wind)',ylabel='physical y m',title=f'Point {i}: native TYPE_S (black), STL (red), AGL 2 m')
 ax.set_aspect('equal');fig.tight_layout();fig.savefig(R/f'point_{i}_z2.png',dpi=160);plt.close(fig)
assert len(result)==80
with (R/'points_80_su.csv').open('w',newline='') as fh:
 w=csv.DictWriter(fh,fieldnames=list(result[0]));w.writeheader();w.writerows(result)
for i,det in detailed.items(): (R/f'point_{i}_geometry.json').write_text(json.dumps(det,indent=2)+'\n')
def median(rs,key):
 v=[r[key] for r in rs if r[key] is not None];return float(np.median(v)) if v else None
groups={}
for name in ('fast','near','slow'):
 rs=[r for r in result if r['class_Su']==name]
 groups[name]={'n':len(rs),'ids':[r['id'] for r in rs],
 'medians':{k:median(rs,k) for k in ('Su_obs','obs_W','wall_m','width_min_m','disk50_cover','upwind_solid_frac','upstream_nearest_solid_m','k_m2s2')},
 'wall_lt1':sum(r['wall_m'] is not None and r['wall_m']<1 for r in rs), 'width_le10':sum(r['width_min_m'] is not None and r['width_min_m']<=10 for r in rs),'reverse_ux_count':sum(r['reverse_ux_proxy'] for r in rs)}
deep=[r for r in result if r['Su_obs']<.4]
summary={'groups':groups,'deep_slow':{'n':len(deep),'ids':[r['id'] for r in deep],'rows':deep},
 'correlations':{key: {'n':len(sub),'spearman_rho':float(spearmanr([r[key] for r in sub],[r['Su_obs'] for r in sub]).correlation)} for key in ('wall_m','width_min_m','disk50_cover','upwind_solid_frac','k_m2s2','obs_W') for sub in [[r for r in result if r[key] is not None]]},
 'flags_shape':list(a.shape),'native_shift_xy_cells':1}
(R/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({'groups':groups,'deep':summary['deep_slow'],'point50':detailed[50],'point74':detailed[74],'correlations':summary['correlations']},indent=2))
