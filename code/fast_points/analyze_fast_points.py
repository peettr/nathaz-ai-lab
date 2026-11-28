"""Offline Case E point/geometry audit; no solver and no input writes."""
from pathlib import Path
import json, math, struct, csv
import numpy as np
from scipy.spatial import cKDTree
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
R=Path(__file__).resolve().parent; L=R.parents[1]; B=L/'wp1b_ibm'; N=L/'wp1_nearwall'
paths={'B2':B/'inflow_ti/B2_offset_samples.json','G0':N/'city_diag_noT/G0_offset_samples_a_r10.json','C1':B/'resolution_crop_v2/C1v2_offset_samples.json','C05':B/'resolution_c05/C05_offset_samples_a_r10.json','C1G0':B/'resolution_split/C1G0_samples.json'}
datasets={k:{r['id']:r for r in json.loads(p.read_text())['rows']} for k,p in paths.items()}
assert len(datasets['B2'])==len(datasets['G0'])==80
stl=B/'inflow_ti/stage_B/case/proj_temp/CaseE_PF.stl'
dt=np.dtype([('normal','<f4',3),('v','<f4',(3,3)),('attr','<u2')])
with stl.open('rb') as f:
 f.read(80); n=struct.unpack('<I',f.read(4))[0]; faces=np.fromfile(f,dtype=dt,count=n)['v']
assert len(faces)==n
tri=faces[:-12].astype(float); z=2.; ends=np.roll(tri,-1,axis=1); za=tri[:,:,2]; zb=ends[:,:,2]
hit=((za<=z)&(z<zb))|((zb<=z)&(z<za)); sel=hit.sum(axis=1)==2
v=tri[sel];e=ends[sel];hh=hit[sel]; t=(z-v[:,:,2])/(e[:,:,2]-v[:,:,2]+(e[:,:,2]==v[:,:,2])*1.)
seg=(v+t[:,:,None]*(e-v))[:,:,:2][hh].reshape(-1,2,2)
# Nearest wall: exact point-to-segment minimum; street widths: x/y ray pairs when defined.
a=seg[:,0,:]; d=seg[:,1,:]-a; dd=np.einsum('ij,ij->i',d,d)
def geometry(p):
 t=np.clip(np.einsum('ij,ij->i',p-a,d)/np.maximum(dd,1e-20),0,1); nearest=a+t[:,None]*d
 dist=np.linalg.norm(nearest-p,axis=1); j=int(np.argmin(dist))
 widths=[]
 for axis in (0,1):
  other=1-axis; lo=a[:,other];hi=seg[:,1,other];cross=((lo<=p[other])&(p[other]<hi))|((hi<=p[other])&(p[other]<lo));use=np.flatnonzero(cross)
  xx=a[use,axis]+(p[other]-lo[use])*(d[use,axis]/(hi[use]-lo[use]))
  left=xx[xx<p[axis]-1e-5];right=xx[xx>p[axis]+1e-5]
  if len(left) and len(right): widths.append({'axis':('x' if axis==0 else 'y'),'width_m':float(right.min()-left.max()),'edge_m':[float(left.max()),float(right.min())]})
 # nearest wall tangent describes local facade, not necessarily a street centerline.
 tangent=d[j]/np.sqrt(dd[j]) if dd[j]>0 else np.array([np.nan,np.nan]);angle=float(np.degrees(np.arccos(np.clip(abs(tangent[0]),0,1))))
 return float(dist[j]),angle,widths
# Upwind blockage: native TYPE_S voxel fraction at z=2 AGL in a 50m x 10m strip, not a line-of-sight measure.
flags=np.memmap(N/'city_stab/stage3_native_flags.npz',dtype='u1',mode='r') if False else None
# stage3 file has only 22 layers; use full native layer if saved; fallback to STL cross section parity.
maskpath=N/'city_stab/ma010_flags_z0_62.npz'
mask=np.load(maskpath); print('native flags keys/shapes',[(k,mask[k].shape) for k in mask.files]);
arr=mask[mask.files[0]]
# Use shape-aware coordinate extraction, verify expected dimensions.
assert arr.shape[-2:]==(500,500),arr.shape
solid=(arr[22] & 1)!=0 if arr.ndim==3 else None
assert solid is not None
out=[]
for id,row in sorted(datasets['B2'].items()):
 x,y=np.asarray(row['xls_xy'])+np.array([250.50008,250.60004]); p=np.array([x,y]);dist,angle,widths=geometry(p)
 ix=int(round(x));iy=int(round(y)); x0=max(0,ix-50);x1=max(0,min(500,ix));y0=max(0,iy-5);y1=min(500,iy+6)
 block=float(solid[y0:y1,x0:x1].mean()) if x1>x0 else None
 obs=row['after']; vals={}
 for name,table in datasets.items():
  if id in table:
   s=table[id]['sample']['plus_dx']; vals[name]={'S_over_W':s['sim_ratio']/obs,'Sstar_over_W':s['exp_ratio']/obs,'Sstar':s['exp_ratio'],'S':s['sim_ratio'],'k':s['tke_m2s2']}
 r=vals['B2']['S_over_W']; cat='快>1.2' if r>1.2 else ('慢<0.8' if r<0.8 else '中0.8–1.2')
 out.append(dict(id=id,xy=[float(x),float(y)],W=obs,category=cat,wall_distance_m=dist,facade_angle_to_wind_deg=angle,street_widths=widths,street_width_min_m=min([w['width_m'] for w in widths],default=None),upwind_solid_fraction_50x11m=block,values=vals))
(R/'points_80.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
with (R/'points_80.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['id','x','y','W','class_S','B2_S/W','B2_Sstar/W','wall_m','facade_angle_deg','street_width_min_m','upwind_solid_fraction','G0_S/W','C1_S/W','C1G0_S/W','C05_S/W'])
 for v in out:
  w.writerow([v['id'],*v['xy'],v['W'],v['category'],v['values']['B2']['S_over_W'],v['values']['B2']['Sstar_over_W'],v['wall_distance_m'],v['facade_angle_to_wind_deg'],v['street_width_min_m'],v['upwind_solid_fraction_50x11m']]+[v['values'].get(k,{}).get('S_over_W') for k in ('G0','C1','C1G0','C05')])
summary={}
for cat in ('快>1.2','中0.8–1.2','慢<0.8'):
 v=[r for r in out if r['category']==cat]
 def median(key):return float(np.median([r[key] for r in v if r[key] is not None])) if v else None
 summary[cat]={'n':len(v),'ids':[r['id'] for r in v],'median_S_over_W':float(np.median([r['values']['B2']['S_over_W'] for r in v])) if v else None,'median_wall_m':median('wall_distance_m'),'median_facade_angle_deg':median('facade_angle_to_wind_deg'),'median_width_m':median('street_width_min_m'),'median_upwind_solid_fraction':median('upwind_solid_fraction_50x11m'),'n_wall_lt1':sum(r['wall_distance_m']<1 for r in v),'n_facade_angle_lt30':sum(r['facade_angle_to_wind_deg']<30 for r in v),'n_width_gt10':sum(r['street_width_min_m'] is not None and r['street_width_min_m']>10 for r in v)}
(R/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
fig,ax=plt.subplots(figsize=(10,10));ax.add_collection(LineCollection(seg,colors='#999999',linewidths=.45,alpha=.7)); p=np.array([r['xy'] for r in out]); c=np.array([r['values']['B2']['S_over_W'] for r in out]);sc=ax.scatter(p[:,0],p[:,1],c=c,cmap='coolwarm',vmin=0,vmax=2,edgecolors='k',linewidths=.25,s=35,zorder=3)
for r in out:
 if r['id'] in (23,25,37,17,50,51,52,54):ax.annotate(str(r['id']),r['xy'],fontsize=7,xytext=(3,3),textcoords='offset points')
fig.colorbar(sc,ax=ax,label='B2 vector mean S / observed W');ax.set(xlim=(0,500),ylim=(0,500),xlabel='solver x (m), west wind +x',ylabel='solver y (m)',title='Case E B2: 80 points at z=2 m; STL section');ax.set_aspect('equal');fig.tight_layout();fig.savefig(R/'fast_points_map.png',dpi=170);plt.close(fig)
print(json.dumps(summary,ensure_ascii=False,indent=2));print('open',[(r['id'],round(r['values']['B2']['S_over_W'],3),round(r['wall_distance_m'],2),round(r['facade_angle_to_wind_deg']),round(r['upwind_solid_fraction_50x11m'],3)) for r in out if r['id'] in (23,25,37,17)])
