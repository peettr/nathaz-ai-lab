"""B2 input-only paired diagnostic, no return-level or standards data."""
import csv,zipfile,json,hashlib,pathlib,math,io,time,sys
import numpy as np,xarray as xr
from climada.hazard.trop_cyclone.trop_cyclone_windfields import tctrack_to_si,_compute_windfields,MODEL_VANG
P=pathlib.Path('/content');out=P/'diag5';out.mkdir(exist_ok=False)
sites=list(csv.DictReader(open(P/'sites_min.csv')));names=[r['site'] for r in sites];SITES=np.array([[float(r['lat']),float(r['lon'])] for r in sites]);assert len(sites)==19
obs=list(csv.DictReader(open(P/'obs_inputs.csv')))
selobs=[r for r in obs if r['pc']!=''];x=np.array([float(r['vmax']) for r in selobs]);y=np.array([float(r['pc']) for r in selobs]);coef=np.polyfit(x,y,2)
rmwobs=[r for r in obs if r['rmw']!=''];min_v,max_v=float(x.min()),float(x.max())
print('OBS',len(obs),len(rmwobs),'fit',coef,flush=True)
def pcfit(v):return np.polyval(coef,np.clip(v,min_v,max_v))
def rmwsample(v,lat,identity):
 # 20-kt wind bin and three latitude bins, fallback to all-lat wind bin,
 # then nearest broader wind bin; deterministic storm/node draw.
 vals=[]
 for a,b,i in zip(np.atleast_1d(v),np.atleast_1d(lat),range(len(np.atleast_1d(v)))):
  vb=round(float(a)/20)*20;zone=0 if b<25 else 1 if b<35 else 2
  pool=[float(r['rmw']) for r in rmwobs if abs(float(r['vmax'])-vb)<=10 and (0 if float(r['lat'])<25 else 1 if float(r['lat'])<35 else 2)==zone]
  if len(pool)<20:pool=[float(r['rmw']) for r in rmwobs if abs(float(r['vmax'])-vb)<=15]
  if len(pool)<20:pool=[float(r['rmw']) for r in rmwobs if abs(float(r['vmax'])-vb)<=30]
  if not pool:pool=[float(r['rmw']) for r in rmwobs]
  seed=int(hashlib.sha256(f'{identity}:{i}:20261014'.encode()).hexdigest()[:16],16)
  vals.append(pool[seed%len(pool)])
 return np.array(vals)
def distances(lat,lon):
 a=np.radians(np.asarray(lat)[:,None]-SITES[:,0]);b=np.radians(np.asarray(lon)[:,None]-SITES[:,1]);q=np.sin(a/2)**2+np.cos(np.radians(lat)[:,None])*np.cos(np.radians(SITES[:,0]))*np.sin(b/2)**2
 return 12742*np.arcsin(np.sqrt(np.clip(q,0,1)))
def track(lat,lon,pc,rmw,vmax,h,source):
 n=len(lat);grid=np.arange((n-1)*int(h*4)+1);old=np.arange(n)*h*4
 def interpolate(a):return np.interp(grid,old,a)
 la=interpolate(lat);lo=interpolate(np.unwrap(np.radians(lon)))*180/np.pi;tm=np.datetime64('2000-01-01')+grid.astype('timedelta64[m]')*15
 return xr.Dataset(data_vars={'lat':('time',la),'lon':('time',lo),'central_pressure':('time',interpolate(pc)),'radius_max_wind':('time',interpolate(rmw)),'max_sustained_wind':('time',interpolate(vmax)),'environmental_pressure':('time',np.full(len(grid),1010.)),'time_step':('time',np.full(len(grid),.25))},coords={'time':tm},attrs={'max_sustained_wind_unit':'knots' if source=='RAFT' else 'm/s','central_pressure_unit':'mbar'})
def predict(data):
 si=tctrack_to_si(data);vectors,ix=_compute_windfields(si,SITES,MODEL_VANG['H08'],max_dist_eye_km=300)
 peak=np.zeros(19,dtype=float)
 if len(ix):peak[ix]=np.linalg.norm(vectors,axis=2).max(axis=0)*1.07
 return peak
rows=[];peaks=[];counts={}
def push(cat,identity,lat,lon,v,pc,rmw,h,vraw):
 d=distances(lat,lon);mask=np.min(d,axis=1)<=500
 if not mask.any():return
 # All eligible raw nodes; native cadence, do not duplicate nodes by nearest station.
 for a,b,c,l,o,di in zip(v[mask],pc[mask],rmw[mask],lat[mask],lon[mask],d[mask].min(axis=1)):
  rows.append((cat,a,b,max(0,1010-b),c,l,o,di))
 counts[cat]=counts.get(cat,0)+1
 if int(hashlib.sha256(str(identity).encode()).hexdigest()[:8],16)%20>=1:return
 ro=rmwsample(v,lat,identity);alt=pcfit(v)
 for variant,p,r in [('base',pc,rmw),('Pc_only',alt,rmw),('RMW_only',pc,ro),('both',alt,ro)]:
  try:
   z=predict(track(lat,lon,p,r,vraw,h,cat))
   for name,value in zip(names,z):peaks.append((cat,identity,name,variant,value))
  except Exception as e:
   print('FAIL',cat,identity,variant,repr(e),flush=True)
 if counts[cat]%1000<2:print(cat,'selected',counts[cat],flush=True)
d=xr.open_dataset(P/'RAFT.NA.v20231016.nc');print('RAFT dims',dict(d.sizes),flush=True)
for i in range(d.sizes['storm'] if 'storm' in d.sizes else 40000):
 la=d['lat'][i].values;lo=d['lon'][i].values;vv=d['vmax'][i].values;pc=d['mslp'][i].values;rm=d['rmax'][i].values
 valid=np.isfinite(la)&np.isfinite(lo)&np.isfinite(pc)&(pc>0)&(rm>0)&(vv>0)
 idx=np.where(valid)[0]
 if len(idx)<2 or np.any(np.diff(idx)!=1):continue
 push('RAFT',i,la[idx].astype(float),lo[idx].astype(float),vv[idx].astype(float),pc[idx].astype(float),rm[idx].astype(float),6,vv[idx].astype(float))
 if i%10000==0:print('RAFT',i,len(rows),flush=True)
d.close()
with open(out/'raft_inputs_checkpoint.csv','w') as f:
 w=csv.writer(f);w.writerow(['catalog','vmax_kt','pc_hpa','dp1010_hpa','rmw_nmi','lat','lon','nearest_site_km']);w.writerows(rows)
with open(out/'raft_peaks_checkpoint.csv','w') as f:
 w=csv.writer(f);w.writerow(['catalog','event','site','variant','peak_ms']);w.writerows(peaks)
print('RAFT CHECKPOINT',len(rows),len(peaks),flush=True)
with zipfile.ZipFile(P/'STORMV4.zip') as z:
 paths=sorted((a for a in z.namelist() if '_NA_' in a),key=lambda a:int(a.rsplit('_',1)[-1].split('.')[0]));assert len(paths)==10,paths
 for file_id,name in enumerate(paths):
  with z.open(name) as f:a=np.loadtxt(f,delimiter=',',dtype=float)
  key=a[:,0].astype('int64')*100+a[:,2].astype('int64');starts=np.r_[0,1+np.where(np.diff(key)!=0)[0]];ends=np.r_[starts[1:],len(a)]
  for b,e in zip(starts,ends):
   c=a[b:e];valid=np.isfinite(c[:,5:10]).all(axis=1)&(c[:,7]>0)&(c[:,9]>0)&(c[:,8]>0)
   if len(c)<2 or not valid.all() or not np.all(np.diff(c[:,3])==1):continue
   identity=file_id*1000000+int(c[0,0])*100+int(c[0,2]);push('STORM',identity,c[:,5],c[:,6]-360,c[:,8]*1.11/0.514444,c[:,7],c[:,9]/1.852,3,c[:,8]*1.11)
  print('STORM file',file_id,len(rows),len(peaks),flush=True)
with open(out/'inputs_raw.csv','w') as f:
 w=csv.writer(f);w.writerow(['catalog','vmax_kt','pc_hpa','dp1010_hpa','rmw_nmi','lat','lon','nearest_site_km']);w.writerows(rows)
with open(out/'paired_peaks.csv','w') as f:
 w=csv.writer(f);w.writerow(['catalog','event','site','variant','peak_ms']);w.writerows(peaks)
(out/'meta.json').write_text(json.dumps(dict(counts=counts,obs_count=len(obs),obs_rmw_count=len(rmwobs),pc_fit_quadratic_coeff=coef.tolist(),sample_method='sha256(event) modulo 20 <1; deterministic RMW per-event-node SHA256',obs_vmax_fit_range=[min_v,max_v],paired_rows=len(peaks)),indent=2))
import zipfile as _zipfile
with _zipfile.ZipFile(P/'diag5_output.zip','w',compression=_zipfile.ZIP_DEFLATED,compresslevel=5) as archive:
 for file in out.iterdir():archive.write(file,arcname=file.name)
print('DONE',counts,len(rows),len(peaks),(P/'diag5_output.zip').stat().st_size,flush=True)