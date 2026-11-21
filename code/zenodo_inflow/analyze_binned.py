import numpy as np,zipfile,json,csv,collections,time
r='/content/zenodo19041698/attempt3';z=zipfile.ZipFile(r+'/boundaryData.zip')
def vec(b):
 a=np.fromstring(b.decode('ascii').replace('(',' ').replace(')',' '),sep=' ');return a.reshape(-1,3)
b=z.read('boundaryData/points');p=vec(b[b.find(b'\n(\n')+1:]);N=len(p)
times=[round(i/10,3) for i in range(301)];s=np.zeros((N,3));ss=np.zeros((N,3));t0=time.time()
for t in times:
 v=vec(z.read('boundaryData/'+str(t).rstrip('0').rstrip('.')+'/U' if t!=0 else 'boundaryData/0/U'))
 s+=v;ss+=v*v
mean=s/len(times);var=np.maximum(0,ss/len(times)-mean**2)
levels=[1.25,2,2.5,5,7.5,10,12.5,15,20,25,30,50,75,100,150,200,250,300,400]
rows=[]
for h in levels:
 mask=abs(p[:,2]*250-h)<=1.25
 if mask.sum()==0:continue
 m=mean[mask].mean(0); k=.5*var[mask].sum(1).mean()
 rows.append(dict(z_full_m=h,n=int(mask.sum()),z_actual_mean_m=float(p[mask,2].mean()*250),Ustream_mps=float(m[0]),Uvector_mps=float(np.linalg.norm(m)),k_temporal_m2s2=float(k),rms_stream_mps=float(np.sqrt(var[mask,0].mean()))))
with open(r+'/profile_binned.csv','w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
print('seconds',time.time()-t0,'rows',rows,flush=True)
# 1 m grid: model 0.004 m spacing; count nearest per lateral/vertical target
meta={'sample_frames':len(times),'sample_interval_s':.1,'bin_halfwidth_full_m':1.25,'point_count':N,'bounds_model_m':[p.min(0).tolist(),p.max(0).tolist()], 'bounds_full_m':[(p*250).min(0).tolist(),(p*250).max(0).tolist()], 'first':rows[0], 'last':rows[-1]}
open(r+'/binned_meta.json','w').write(json.dumps(meta,indent=2))
