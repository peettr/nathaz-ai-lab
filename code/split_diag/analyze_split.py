"""Read-only input, offline Case E pointwise geometry / flow association audit."""
from pathlib import Path
import csv,json, math
import numpy as np
from scipy.stats import spearmanr
R=Path(__file__).resolve().parent
L=R.parents[1]
fast=json.loads((L/'wp1b_ibm/fast_points/points_80.json').read_text())
paths={'B2':L/'wp1b_ibm/inflow_ti/B2_offset_samples.json',
 'E1':L/'method_study/E1_split_ground/E1_offset_samples.json',
 'Gz2':L/'wp1_nearwall/city_z0/Gz2_offset_samples_a_r10.json',
 'S1c':L/'method_study/S1c_sgs_damp/offset_samples_a_r10.json'}
tables={tag:{r['id']:r for r in json.loads(p.read_text())['rows']} for tag,p in paths.items()}
assert all(set(t)==set(range(1,81)) for t in tables.values())
mask=np.load(L/'wp1_nearwall/city_stab/ma010_flags_z0_62.npz'); a=mask[mask.files[0]]
assert a.shape[-2:]==(500,500),a.shape
# Native flags as a geometry proxy, only through z=62. z=20 ground; upper roofs censored.
solid=(a[21:63]&1)!=0
height=np.where(solid,np.arange(21,63)[:,None,None],0).max(axis=0)-20
height=np.maximum(height,0)
# x/y indices in native array follow [z,y,x], and west-wind flows toward +x.
rows=[]
for v in fast:
 i=v['id']; x,y=v['xy']; ix=int(round(x));iy=int(round(y)); x0=max(0,ix-50);x1=min(500,ix+51);y0=max(0,iy-50);y1=min(500,iy+51)
 yy,xx=np.mgrid[y0:y1,x0:x1]; disk=((xx-x)**2+(yy-y)**2)<=2500
 local=height[y0:y1,x0:x1][disk]
 cover=float(np.mean(local>0)); mean_h=float(np.mean(local[local>0])) if (local>0).any() else None
 # Nearest upstream building along narrow 11 m strip at probe z=2, not a verified streamline.
 xs=np.arange(max(0,ix-50),ix); sy=height[max(0,iy-5):min(500,iy+6),max(0,ix-50):ix]
 up=np.argwhere(sy>=2)
 if len(up):
  j=int(up[:,1].max()); near_dist=float(x-(max(0,ix-50)+j)); up_height=float(sy[:,j][sy[:,j]>0].max())
 else: near_dist=None;up_height=None
 widths=v['street_widths']; wx=next((w['width_m'] for w in widths if w['axis']=='x'),None);wy=next((w['width_m'] for w in widths if w['axis']=='y'),None)
 if wx is not None and wy is not None:
  # Opposing-wall width is cross-street; narrower y => x-oriented street.
  axis='x_proxy' if wy<wx else 'y_proxy'; ang=0 if axis=='x_proxy' else 90
 else: axis='unknown';ang=None
 sx=tables['B2'][i]['sample']['plus_dx']; uv=sx['mean_velocity_mps']; obs=v['W'];
 # k normalized by squared mean-vector speed. This is a local intensity proxy, not observed k.
 U=np.linalg.norm(uv); k=sx['tke_m2s2']; k_ratio=float(k/(U*U)) if U>0 else None
 rec={'id':i,'x':x,'y':y,'obs_W':obs,'S_B2_W':v['values']['B2']['S_over_W'],'Sstar_B2_W':v['values']['B2']['Sstar_over_W'],
  'class_S':v['category'],'wall_m':v['wall_distance_m'],'width_x_m':wx,'width_y_m':wy,'width_min_m':v['street_width_min_m'],
  'street_axis_proxy':axis,'axis_wind_angle_proxy_deg':ang,'facade_tangent_deg':v['facade_angle_to_wind_deg'],
  'upwind_11m_strip_solid_50m':v['upwind_solid_fraction_50x11m'],
  'upstream_nearest_solid_m':near_dist,'upstream_nearest_solid_height_capped_m':up_height,
  'disk50_building_plan_fraction':cover,'disk50_mean_building_height_capped_m':mean_h,
  'k_B2_m2s2':k,'k_over_mean_speed2':k_ratio,'B2_ux_mps':uv[0],
  'open_proxy':bool(v['wall_distance_m']>=5 and cover<.2),'junction_proxy':bool(wx is not None and wy is not None and min(wx,wy)>=20),
  'reverse_ux_proxy':bool(uv[0]<0)}
 for tag in paths:
  s=tables[tag][i]['sample']['plus_dx']; assert abs(tables[tag][i]['after']-obs)<1e-7
  for field,key in [('S','sim_ratio'),('Sstar','exp_ratio')]:
   rec[f'{tag}_{field}']=s[key];rec[f'{tag}_{field}_W']=s[key]/obs;rec[f'{tag}_{field}_signed_error']=s[key]-obs
 rows.append(rec)
with (R/'points_80.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
fast10=[r for r in rows if r['class_S']=='快>1.2'];slow41=[r for r in rows if r['class_S']=='慢<0.8'];middle=[r for r in rows if r['class_S']=='中0.8–1.2']
def summarize(rs):
 fields=['obs_W','wall_m','width_min_m','upstream_nearest_solid_m','upstream_nearest_solid_height_capped_m','disk50_building_plan_fraction','disk50_mean_building_height_capped_m','k_B2_m2s2','k_over_mean_speed2','upwind_11m_strip_solid_50m']
 return {'n':len(rs),'ids':[r['id'] for r in rs], 'medians':{f:(float(np.median([r[f] for r in rs if r[f] is not None])) if any(r[f] is not None for r in rs) else None) for f in fields},
  'x_street_proxy':sum(r['street_axis_proxy']=='x_proxy' for r in rs),'y_street_proxy':sum(r['street_axis_proxy']=='y_proxy' for r in rs),'unknown_axis':sum(r['street_axis_proxy']=='unknown' for r in rs),
  'wall_lt1':sum(r['wall_m']<1 for r in rs),'width_le10':sum(r['width_min_m'] is not None and r['width_min_m']<=10 for r in rs),'open_proxy':sum(r['open_proxy'] for r in rs),'junction_proxy':sum(r['junction_proxy'] for r in rs),'reverse_ux_proxy':sum(r['reverse_ux_proxy'] for r in rs)}
features=['x','wall_m','width_min_m','facade_tangent_deg','upstream_nearest_solid_m','upstream_nearest_solid_height_capped_m','disk50_building_plan_fraction','disk50_mean_building_height_capped_m','upwind_11m_strip_solid_50m','k_B2_m2s2','k_over_mean_speed2','obs_W']
corr={}
for target in ('B2_S_W','B2_Sstar_W'):
 corr[target]={}
 for feat in features:
  sub=[r for r in rows if r[feat] is not None and np.isfinite(r[feat]) and np.isfinite(r[target])]
  rho,p=spearmanr([r[feat] for r in sub],[r[target] for r in sub]);corr[target][feat]={'n':len(sub),'spearman_rho':float(rho),'p_exploratory':float(p)}
# Through-origin scale and affine fit. Report per-point residual and group shifts; no cross-run causal claim.
scale={};changes={}
for field in ('S','Sstar'):
 base=np.array([r[f'B2_{field}'] for r in rows]); scale[field]={}
 for tag in ('E1','Gz2','S1c'):
  other=np.array([r[f'{tag}_{field}'] for r in rows]); c=float(base@other/(base@base)); resid=other-c*base
  a1,b1=np.polyfit(base,other,1); affres=other-(a1*base+b1)
  scale[field][tag]={'slope_through_origin':c,'rmse':float(np.sqrt(np.mean(resid**2))),'mae':float(np.mean(np.abs(resid))),'relative_rmse_to_other_mean':float(np.sqrt(np.mean(resid**2))/np.mean(other)),
   'affine_slope':float(a1),'affine_intercept':float(b1),'affine_rmse':float(np.sqrt(np.mean(affres**2))),
   'residual_fast_mean':float(np.mean([resid[r['id']-1] for r in fast10])),'residual_slow_mean':float(np.mean([resid[r['id']-1] for r in slow41]))}
 changes[field]={}
 for tag in ('E1','Gz2','S1c'):
  changes[field][tag]={g:{'median_ratio_to_B2':float(np.median([r[f'{tag}_{field}']/r[f'B2_{field}'] for r in rs if r[f'B2_{field}']>1e-6])),
   'mean_signed_error_change':float(np.mean([r[f'{tag}_{field}_signed_error']-r[f'B2_{field}_signed_error'] for r in rs])),
   'overcount':sum(r[f'{tag}_{field}_W']>1.2 for r in rs)} for g,rs in [('fast10',fast10),('slow41',slow41)]}
# Geometric variables are not independent, so no trained classifier from 80 samples.
summary={'groups':{'fast10':summarize(fast10),'middle29':summarize(middle),'slow41':summarize(slow41)},'spearman':corr,'scaling':scale,'paired_changes':changes,
 'source_paths':{k:str(v) for k,v in paths.items()},'flags_shape':list(a.shape)}
(R/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'groups':summary['groups'],'scaling':scale,'paired_changes':changes,'top_corr':{k:sorted(v.items(),key=lambda p:abs(p[1]['spearman_rho']),reverse=True)[:7] for k,v in corr.items()}},ensure_ascii=False,indent=2))
