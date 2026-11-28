import zipfile,re,json,os,numpy as np,collections,math,time,csv
root='/content/zenodo19041698/attempt3'; zf=zipfile.ZipFile(root+'/boundaryData.zip')
def vectors(raw):
 s=raw.decode('ascii',errors='replace')
 v=np.fromstring(s.replace('(',' ').replace(')',' '),sep=' ')
 return v.reshape((-1,3))
praw=zf.read('boundaryData/points');pts=vectors(praw[praw.find(b'\n(\n')+1:]);N=len(pts)
files={round(float(x.split('/')[1]),3):x for x in zf.namelist() if x.endswith('/U')}
print('POINTS',N,'bounds',pts.min(0),pts.max(0),flush=True)
spacing={}
for j,name in [(0,'x'),(1,'y'),(2,'z')]:
 u=np.unique(np.round(pts[:,j],7));d=np.diff(u);spacing[name]=dict(unique_count=len(u),min_nonzero=float(d[d>1e-7].min()) if len(d) else None,median_nonzero=float(np.median(d[d>1e-7])) if len(d) else None,common=np.unique(np.round(d,7),return_counts=True)[0][:5].tolist())
print('spacing',spacing,flush=True)
target=[0,1,2,5,10,15,20,25,30,50,75,100,150,200,250]
# height z in model meters, compare at equivalent full scale 250x; bin ±0.75 full meters or nearest plane
levels=np.unique(np.round(pts[:,2],8))
selected={}
for h in target:
 near=levels[np.argmin(abs(levels-h/250))];ind=np.where(abs(pts[:,2]-near)<1e-7)[0]
 selected[h]=dict(z_model=float(near),n=int(len(ind)),ids=ind)
print('selected',[(h,s['z_model'],s['n']) for h,s in selected.items()],flush=True)
# all points temporal moments, sampled 0.1 s over 30 s
T=np.linspace(0,30,301);s=np.zeros((N,3),dtype=np.float64);ss=np.zeros((N,3),dtype=np.float64)
t0=time.time();snap={}
for i,t in enumerate(T):
 key=round(float(t),3);arr=vectors(zf.read(files[key]));assert len(arr)==N,(key,len(arr),N)
 s+=arr;ss+=arr*arr
 if i in (0,150,300):snap[str(key)]=dict(min=arr.min(0).tolist(),max=arr.max(0).tolist(),mean=arr.mean(0).tolist())
 if (i+1)%75==0:print('SAMPLED',i+1,'seconds',round(time.time()-t0,1),flush=True)
mean=s/len(T);var=np.maximum(0,ss/len(T)-mean**2);k=.5*var.sum(axis=1)
rows=[]
for h,v in selected.items():
 ix=v['ids'];mv=mean[ix].mean(axis=0);kt=k[ix].mean(); spatial=mean[ix,0].std()
 rows.append(dict(z_full_m=h,z_model_m=v['z_model'],point_count=v['n'],mean_Ux_mps=float(mv[0]),mean_Uy_mps=float(mv[1]),mean_Uz_mps=float(mv[2]),resolved_k_m2s2=float(kt),rms_Ux_mps=float(np.sqrt(var[ix,0].mean())),spatial_std_mean_Ux=float(spatial)))
with open(root+'/profile_sampled.csv','w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
meta=dict(source='https://doi.org/10.5281/zenodo.19041698',sampling='301 evenly spaced frames t=0..30 s, delta 0.1 s; temporal pointwise variance then lateral average; nearest available z plane, not full 30001-frame statistics',point_count=N,points_min=pts.min(0).tolist(),points_max=pts.max(0).tolist(),spacing=spacing,first_last_snapshots=snap,frames=30001,dt_s=0.001,sample_frames=len(T),sample_elapsed_s=time.time()-t0,velocity_sample_range=[float(np.min(mean[:,0])),float(np.max(mean[:,0]))],z_unique_count=len(levels))
open(root+'/summary.json','w').write(json.dumps(meta,indent=2))
print('DONE',json.dumps({k:meta[k] for k in ('point_count','points_min','points_max','sample_elapsed_s','z_unique_count')},indent=2),flush=True)
print('PROFILE',rows,flush=True)
