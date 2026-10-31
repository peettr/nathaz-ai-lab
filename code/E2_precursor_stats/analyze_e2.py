import zipfile,numpy as np,json,csv,time,os
from scipy.spatial import Delaunay
r='/content/e2'; t0=time.time(); zf=zipfile.ZipFile(r+'/parallel.zip')
def vec(raw):
 s=raw.decode('ascii',errors='replace'); a=np.fromstring(s.replace('(',' ').replace(')',' '),sep=' '); return a.reshape(-1,3)
b=zf.read('boundaryData/points'); pts=vec(b[b.find(b'\n(\n')+1:]); n=len(pts)
yz=np.round(pts[:,1:],8); uq,inv,counts=np.unique(yz,axis=0,return_inverse=True,return_counts=True)
tri=Delaunay(uq); face=uq[tri.simplices]; area=.5*abs(np.cross(face[:,1]-face[:,0],face[:,2]-face[:,0])); wa=np.bincount(tri.simplices.ravel(),weights=np.repeat(area/3,3),minlength=len(uq)); w=wa[inv]/counts[inv]
# guard duplicate positions: split Voronoi/triangular vertex weight equally
mask=abs(pts[:,1])<=.799; w=w*mask
names={round(float(x.split('/')[1]),6):x for x in zf.namelist() if x.endswith('/U')}; alltime=sorted(names)
sel=[t for t in alltime if 10<=t<=30 and abs(t*100-round(t*100))<1e-5]
print('FRAMES',len(alltime),'selected',len(sel),'step_range',alltime[:3],alltime[-3:],'duplicates',int((counts-1).clip(0).sum()),'points',n,'triangles',len(area),flush=True)
s=np.zeros((n,3),np.float64);ss=np.zeros((n,3),np.float64)
for i,t in enumerate(sel):
 a=vec(zf.read(names[t])); assert a.shape==(n,3),(t,a.shape)
 s+=a;ss+=a*a
 if (i+1)%200==0: print('PROGRESS',i+1,round(time.time()-t0,1),flush=True)
m=s/len(sel); var=np.maximum(0,ss/len(sel)-m*m); k=.5*var.sum(1)
heights=[1.25,2,2.5,5,7.5,10,12.5,15,15.9,20,25,30,50,75,100,150,200,250,300,400]
rows=[]
for h in heights:
 ids=(abs(pts[:,2]*250-h)<=1.25)&mask; ww=w[ids]; sw=ww.sum()
 if sw==0:continue
 ux=np.average(m[ids,0],weights=ww); kk=np.average(k[ids],weights=ww)
 rows.append(dict(z_target_full_m=h,z_mean_full_m=float(np.average(pts[ids,2]*250,weights=ww)),n=int(ids.sum()),effective_area_model_m2=float(sw),Ustream_mps=float(ux),k_temporal_m2s2=float(kk)))
with open(r+'/profile_weighted.csv','w',newline='') as f:
 writer=csv.DictWriter(f,rows[0].keys());writer.writeheader();writer.writerows(rows)
meta=dict(source='10.5281/zenodo.19041698',points=n,unique_points=len(uq),duplicate_count=int((counts-1).clip(0).sum()),triangles=len(area),total_area=float(wa.sum()),retained_area=float(w.sum()),retained_points=int(mask.sum()),all_frames=len(alltime),all_dt_min=float(np.min(np.diff(alltime))),all_dt_max=float(np.max(np.diff(alltime))),used_frames=len(sel),used_first=sel[0],used_last=sel[-1],used_stride_s=.01,elapsed_s=time.time()-t0,fields=sorted(set(x.split('/')[-1] for x in zf.namelist() if x.startswith('boundaryData/') and x.count('/')==2)))
open(r+'/stats.json','w').write(json.dumps(meta,indent=2));print('DONE',json.dumps(meta),flush=True)
