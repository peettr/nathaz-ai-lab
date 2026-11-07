import pathlib,json,numpy as np
P=pathlib.Path('/content/l264a100');T=P/'texas';R=P/'AERO_ODE/AERO_Surface_WD/Hrrr_rb/data';y,x=np.load(T/'west_offsets.npy');shape=np.load(R/'hrrr_west_lat.npy').shape;h,w=shape
v=np.load(T/'VGTYP.npy')[y:y+h,x:x+w].astype(int);s=np.load(T/'SFCR.npy')[y:y+h,x:x+w]
from scipy.ndimage import uniform_filter
G=np.load(T/'HGT.npy')[y:y+h,x:x+w];dy,dx=np.gradient(G.astype(float),3000.,3000.)
def metric(a,b):
 a=a.reshape(-1);b=b.reshape(-1);return {'r':float(np.corrcoef(a,b)[0,1]) if a.std() and b.std() else None,'max_abs':float(np.max(abs(a-b))),'mean_abs':float(np.mean(abs(a-b)))}
channels={}
for name in ('urban_mask','forest_mask','cropland_mask','grassland_mask'):
 r=np.load(R/(name+'.npy'));original={'urban_mask':[13],'forest_mask':[1,2,3,4,5],'cropland_mask':[12,14],'grassland_mask':[6,7,8,9,10]}[name]
 p=np.isin(v,original).astype(float)
 channels[name]={'original_mapping':original,**metric(p,r),'fraction_mismatch':float(np.mean(p!=r)),'west_fraction':float(np.mean(r)),'hrrr_fraction':float(np.mean(p))}
# compare several transparent orientation/normalization candidates; not pick by metric for test, just diagnose.
for name,p in [('aspect_sin',-dx/np.maximum(np.hypot(dx,dy),1e-12)),('aspect_cos',-dy/np.maximum(np.hypot(dx,dy),1e-12)),('aspect_cos_opposite',dy/np.maximum(np.hypot(dx,dy),1e-12))]:
 ref=np.load(R/(('aspect_cos' if 'cos' in name else name)+'.npy'))
 channels[name]=metric(p,ref)
for name,p in [('roughness_direct_log',np.log(np.maximum(s,1e-6))),('roughness_norm_log',None)]:
 if p is None:
  q=np.log(np.maximum(s,1e-6));p=(q-q.mean())/(q.std()+1e-6)
 channels[name]=metric(p,np.load(R/'roughness_log_z0_norm.npy'))
T.joinpath('west_diagnostics.json').write_text(json.dumps(channels,indent=2));print(json.dumps(channels,indent=2))
