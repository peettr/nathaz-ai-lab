"""Read-only Case E registration diagnostic; generates only _r2 products."""
from pathlib import Path
import csv, json
import numpy as np
from scipy.ndimage import distance_transform_edt
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sys
ROOT=Path('./22_Lab/06_Logs/luw')
SRC=Path('./.cache/dwt-luw-eval/examples/example_ProfileResearch_noDEM')
sys.path.insert(0,str(ROOT/'pydeps'))
import xlrd
D=np.dtype([('normal','<f4',(3,)),('v','<f4',(3,3)),('attr','<u2')])
def triangles(p):
    return np.fromfile(p,dtype=D,offset=84)['v'].astype(float)
raw=triangles(SRC/'building_db/rawbuildings.stl')
pf=triangles(SRC/'proj_temp/CaseE_PF.stl')
# Raw triangles appear as first 9198 triangles of PF, followed by 12 triangles defining the base.
delta=pf[:len(raw)]-raw
shift=np.median(delta.reshape(-1,3),axis=0)
print('RAW-to-PF per-vertex shift median',shift,'max deviation',np.abs(delta-shift).max(axis=(0,1)))
book=xlrd.open_workbook(str(SRC/'CaseE(Niigata).xls'))
s=book.sheet_by_name('Geometry&Points')
ids=np.array([int(s.cell_value(i,1)) for i in range(2,82)])
pts=np.array([[float(s.cell_value(i,j)) for j in (2,3)] for i in range(2,82)])
# Open horizontal ray from z=2: roof triangles are horizontal above that elevation.
roof=raw[np.all(raw[:,:,2]>2.,axis=1)]
roof=roof[(np.ptp(roof[:,:,2],axis=1)<.001)]
print('roof triangles',len(roof),'height range',roof[:,:,2].min(),roof[:,:,2].max())
# Barycentric containment in roof triangulation.
def in_tri(points, tris):
    a=tris[:,0,:2]; b=tris[:,1,:2]-a; c=tris[:,2,:2]-a
    q=points[:,None,:]-a[None,:,:]
    den=b[:,0]*c[:,1]-b[:,1]*c[:,0]
    ok=np.abs(den)>1e-10
    uu=(q[:,:,0]*c[None,:,1]-q[:,:,1]*c[None,:,0])/np.where(ok,den,1)[None,:]
    vv=(b[None,:,0]*q[:,:,1]-b[None,:,1]*q[:,:,0])/np.where(ok,den,1)[None,:]
    return np.any(ok[None,:] & (uu>=-1e-7)&(vv>=-1e-7)&(uu+vv<=1+1e-7),axis=1)
# Roof polygons can have superposed triangles; occupancy union is still valid.
inside=in_tri(pts,roof)
# Horizontal exterior walls: vertical triangle edge at the ground or any roof height.
v=raw
vertical=v[(np.ptp(v[:,:,2],axis=1)>0.5)&(np.ptp(v[:,:,0],axis=1)<1000)]
segments=[]
for t in vertical:
    xy=t[:,:2]
    for i,j in ((0,1),(1,2),(2,0)):
        if abs(t[i,2]-t[j,2])<.001 and np.linalg.norm(xy[i]-xy[j])>1e-5:
            segments.append((xy[i],xy[j]))
segments=np.array(segments)
def distance(points,segments):
    a=segments[:,0]; d=segments[:,1]-a
    p=points[:,None,:]-a
    t=np.clip(np.sum(p*d[None,:,:],axis=2)/np.maximum(np.sum(d*d,axis=1),1e-20),0,1)
    return np.min(np.linalg.norm(p-t[:,:,None]*d[None,:,:],axis=2),axis=1)
dist=distance(pts,segments)
npz=np.load(ROOT/'caseE_N_avg_z2_slice.npz')
dx=float(npz['spacing']); u=npz['u']; origin=npz['origin']
# Diff between original midpoint hypothesis and raw-STL-verified shift in PF frame.
old_shift=np.array([2022.500153/2,1996.500092/2]); new_shift=shift[:2]
uref=3.9286416
obs={}
for k,name in (('before','Results (Before Construction)'),('after','Results (After Construction)')):
    sh=book.sheet_by_name(name)
    obs[k]=np.array([float(sh.cell_value(i+1,2)) for i in range(2,82)])
def sampled(offset):
    xy=pts+offset
    xi=(xy[:,0]-origin[0])/dx; yi=(xy[:,1]-origin[1])/dx
    i=np.floor(xi).astype(int); j=np.floor(yi).astype(int)
    a=xi-i; b=yi-j
    out=np.full(len(pts),np.nan)
    for n in range(len(pts)):
        if 0<=i[n]<u.shape[1]-1 and 0<=j[n]<u.shape[0]-1:
            vec=(1-a[n])*(1-b[n])*u[j[n],i[n]]+a[n]*(1-b[n])*u[j[n],i[n]+1]+(1-a[n])*b[n]*u[j[n]+1,i[n]]+a[n]*b[n]*u[j[n]+1,i[n]+1]
            out[n]=np.linalg.norm(vec)/uref
    return out
metrics={}
for label,offset in (('old_midpoint',old_shift),('raw_stl_shift',new_shift)):
    sim=sampled(offset)
    metrics[label]={'shift_m':offset.tolist(),'solid':int(inside.sum()),'within_1cell_of_wall':int((dist<=dx).sum()),'solid_or_near_wall':int((inside|(dist<=dx)).sum()),'median_wall_distance_m':float(np.median(dist)),'point_sim':{'n_finite':int(np.isfinite(sim).sum()),'n_lt_0.03':int((sim<.03).sum()),'mean':float(np.nanmean(sim))}}
    for state,arr in obs.items():
        valid=np.isfinite(sim)&np.isfinite(arr)
        metrics[label][state]={'n':int(valid.sum()),'mae':float(np.mean(np.abs(sim[valid]-arr[valid]))),'r':float(np.corrcoef(sim[valid],arr[valid])[0,1]),'obs_mean':float(np.mean(arr[valid])),'sim_mean':float(np.mean(sim[valid])),'mean_ratio':float(np.mean(sim[valid])/np.mean(arr[valid]))}
    with (ROOT/f'CaseE_N_points_{label}_r2.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['id','xls_x','xls_y','distance_to_raw_STL_wall_m','inside_roof_footprint_z2','within_one_dx_wall','sim_mean_speed_over_U15p9','tunnel_before_N','tunnel_after_N'])
        for row in zip(ids,pts[:,0],pts[:,1],dist,inside,dist<=dx,sim,obs['before'],obs['after']):w.writerow(row)
print(json.dumps(metrics,indent=2))
with (ROOT/'CaseE_registration_metrics_r2.json').open('w') as f:json.dump({'raw_to_PF_shift_m':shift.tolist(),'max_translation_error_m':np.abs(delta-shift).max(axis=(0,1)).tolist(),'raw_bounds_m':[raw.reshape(-1,3).min(axis=0).tolist(),raw.reshape(-1,3).max(axis=0).tolist()],'xls_only_states':['Before Construction','After Construction'],'one_grid_m':dx,'metrics':metrics},f,indent=2)
fig,ax=plt.subplots(figsize=(10,9))
# Each roof triangle projected as footprint; very light gray to make individual building shapes visible.
from matplotlib.collections import PolyCollection
ax.add_collection(PolyCollection(roof[:,:,:2],facecolors='#777777',edgecolors='none',alpha=.7))
ax.scatter(pts[~inside,0],pts[~inside,1],s=45,facecolors='none',edgecolors='blue',label='measuring point (free by roof test)')
ax.scatter(pts[inside,0],pts[inside,1],s=45,facecolors='red',edgecolors='white',linewidths=.5,label='under roof at z=2 m')
for k,(x,y) in enumerate(pts):
    ax.annotate(str(ids[k]),(x,y),xytext=(2,2),textcoords='offset points',fontsize=6)
ax.set(xlim=(-220,220),ylim=(-220,220),xlabel='raw STL X (m); xls X assumed same',ylabel='raw STL Y (m); xls Y assumed same',title='AIJ Case E: xls point overlay on raw STL roof footprint, z=2 m\nAssumed identity registration (NOT independently certified)')
ax.set_aspect('equal');ax.grid(alpha=.25);ax.legend(loc='upper left',fontsize=8)
fig.savefig(ROOT/'CaseE_points_footprint_r2.png',dpi=160,bbox_inches='tight');plt.close(fig)
