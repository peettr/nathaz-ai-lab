"""Build bounded WD/TX static inputs on the Colab VM; explicit Table 4 lookup required."""
import pathlib,json,h5py
import numpy as np
from scipy.ndimage import uniform_filter
p=pathlib.Path('/content/l264a100');t=p/'texas';root=p/'AERO_ODE'
lookup=json.loads((t/'table4_z0.json').read_text())
assert set(map(int,lookup))>=set(range(18)) and all(float(v)>0 for v in lookup.values()),'Table4 lookup incomplete'
yw,xw=map(int,np.load(t/'west_offsets.npy'));yt,xt=0,810;h,w=440,408
west=root/'AERO_Surface_WD/Hrrr_rb/data'
coords={key:np.load(t/(key+'.npy')) for key in ('noaa_lat','noaa_lon')}
hgt=np.load(t/'HGT.npy',mmap_mode='r');vg=np.load(t/'VGTYP.npy',mmap_mode='r')

def zscore(a):return (a-a.mean())/(a.std()+1e-6)
def generate(label,y,x):
 d=t/(label+'_static');d.mkdir(exist_ok=True)
 g=np.array(hgt[y:y+h,x:x+w],dtype=np.float32); vraw=np.array(vg[y:y+h,x:x+w],dtype=np.int32)
 # NOAA HRRR MODIS VGTYP class 17 is water; Table 4 labels water 0.
 # This crosswalk is an explicit source-encoding assumption, not a fitted parameter.
 v=np.where(vraw==17,0,vraw)
 lat=coords['noaa_lat'][y:y+h,x:x+w];lon=coords['noaa_lon'][y:y+h,x:x+w]
 dy,dx=np.gradient(g.astype(np.float64),3000.,3000.);mag=np.maximum(np.hypot(dx,dy),1e-12)
 # Match the delivered WD orientation; do NOT z-score sine/cosine (reference range [-1,1]).
 feat={'slope':zscore(np.arctan(np.hypot(dx,dy))),
       'tpi':zscore(g-uniform_filter(g,size=5,mode='nearest')),
       'aspect_sin':-dx/mag,'aspect_cos':dy/mag,
       'urban_mask':v==13,'forest_mask':np.isin(v,[1,2,3,4,5]),
       'cropland_mask':np.isin(v,[12,14]),'grassland_mask':np.isin(v,[6,7,8,9,10])}
 missing=set(np.unique(v).tolist())-set(map(int,lookup))
 if missing:raise RuntimeError(f'VGTYP classes absent from Table4 mapping: {missing}')
 z0=np.zeros(v.shape,dtype=np.float64)
 for k,val in lookup.items():z0[v==int(k)]=float(val)
 feat['roughness_log_z0_norm']=zscore(np.log(z0))
 for name,a in feat.items():np.save(d/(name+'.npy'),np.asarray(a,dtype=np.float32))
 for name,a in [('hrrr_west_lat',lat),('hrrr_west_lon',lon)]:np.save(d/(name+'.npy'),a)
 with h5py.File(d/'west_geo_interpolate.h5','x') as f:f.create_dataset('fields',data=g[None])
 ad=t/(label+'_air')/'data';ad.mkdir(parents=True,exist_ok=True)
 for name in ('west_geo_interpolate.h5','hrrr_west_lat.npy','hrrr_west_lon.npy'):(ad/name).symlink_to(d/name)
 print(label,'offset',y,x,'VGTYP unique/count',np.unique(v,return_counts=True),'corners',[(float(lat[i,j]),float(((lon[i,j]+180)%360)-180)) for i,j in [(0,0),(0,-1),(-1,0),(-1,-1)]],flush=True)
 return d,feat,g,lat,lon
r,feat,g,lat,lon=generate('west',yw,xw)
def met(a,b):
 a=np.asarray(a,dtype=np.float64);b=np.asarray(b,dtype=np.float64)
 return {'corr':float(np.corrcoef(a.ravel(),b.ravel())[0,1]) if a.std() and b.std() else None,'max_abs_diff':float(np.max(abs(a-b))),'mean_abs_diff':float(np.mean(abs(a-b)))}
with h5py.File(west/'west_geo_interpolate.h5') as f: georef=f['fields'][0]
res={'geo_raw':met(g,georef)}
for name,a in feat.items():res[name]=met(a,np.load(west/(name+'.npy')))
(t/'west_comparison_corrected.json').write_text(json.dumps(res,indent=2));print('WEST_COMPARISON',json.dumps(res),flush=True)
r,feat,g,lat,lon=generate('texas',yt,xt)
overlap=max(0,min(yt+h,yw+h)-max(yt,yw))*max(0,min(xt+w,xw+w)-max(xt,xw))/(h*w)
meta={'west_offset':[yw,xw],'texas_offset':[yt,xt],'shape':[h,w],'overlap_fraction':overlap,'strict_fraction':1-overlap,'corners':[(float(lat[i,j]),float(((lon[i,j]+180)%360)-180)) for i,j in [(0,0),(0,-1),(-1,0),(-1,-1)]]}
(t/'window.json').write_text(json.dumps(meta,indent=2));(t/'build_static.done').write_text('ok\n')
print('WINDOW',json.dumps(meta),flush=True)
