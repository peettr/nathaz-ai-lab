"""B2 passage counts at frozen stations. Input-only, no return levels or standards."""
import csv, json, zipfile, hashlib, pathlib, collections
from datetime import datetime
import numpy as np, xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=pathlib.Path(__file__).resolve().parent; B=P.parent
sites=list(csv.DictReader(open(P/'sites_min.csv'))); ids=[r['site'] for r in sites]
lat_s=np.array([float(r['lat']) for r in sites]);lon_s=np.array([float(r['lon']) for r in sites]);assert len(ids)==19
segs={'TX':ids[:3],'LA_to_Panhandle':ids[3:9],'FL_peninsula':ids[9:16],'Carolinas':ids[16:]}
RINGS=('RMW_le1','RMW_1to3','km_le50','km_le100')
cols=['source','event','year','site','segment','zone','category','vmax_kt','dp1010_hpa','distance_km','rmw_nmi','node_time','rmw_available_nodes','all_nodes']
rows=[];coverage=collections.Counter();eligible=collections.Counter()
def distance(lat,lon):
 a=np.radians(np.asarray(lat)[:,None]-lat_s[None,:]);b=np.radians(np.asarray(lon)[:,None]-lon_s[None,:]);q=np.sin(a/2)**2+np.cos(np.radians(lat)[:,None])*np.cos(np.radians(lat_s))[None,:]*np.sin(b/2)**2
 return 12742*np.arcsin(np.sqrt(np.clip(q,0,1)))
def cat(v):return 'Cat4-5' if v>=114 else 'Cat3+' if v>=96 else 'Cat1-2' if v>=64 else 'TS' if v>=35 else None
# Strongest native tropical TS/HU node in zone per event-site; one event counted once per zone.
def add(source,event,year,lat,lon,v,pc,rmw,times=None):
 lat=np.asarray(lat,float);lon=np.asarray(lon,float);v=np.asarray(v,float);pc=np.asarray(pc,float);rmw=np.asarray(rmw,float)
 good=np.isfinite(lat)&np.isfinite(lon)&np.isfinite(v)&(v>=35)
 if not good.any():return
 lat,lon,v,pc,rmw=lat[good],lon[good],v[good],pc[good],rmw[good]
 if times is not None:times=np.asarray(times)[good]
 d=distance(lat,lon); near=np.any(d<=100,axis=0)
 for j,s in enumerate(ids):
  seg=next(k for k,ss in segs.items() if s in ss)
  rr=rmw*1.852; valid=np.isfinite(rr)&(rr>0)
  if source=='HURDAT2' and np.any(d[:,j]<=300):
   coverage[(s,'nodes_near300')]+=int(np.sum(d[:,j]<=300));coverage[(s,'rmw_near300')]+=int(np.sum((d[:,j]<=300)&valid))
  for zone,mask in [('RMW_le1',valid&(d[:,j]<=rr)),('RMW_1to3',valid&(d[:,j]>rr)&(d[:,j]<=3*rr)),('km_le50',d[:,j]<=50),('km_le100',d[:,j]<=100)]:
   if not mask.any():continue
   indices=np.where(mask)[0];k=indices[np.argmax(v[indices])]
   rows.append([source,str(event),str(year),s,seg,zone,cat(v[k]),float(v[k]),float(max(0,1010-pc[k])) if np.isfinite(pc[k]) and pc[k]>0 else '',float(d[k,j]),float(rmw[k]) if valid[k] else '',str(times[k]) if times is not None else '',int(valid.sum()),len(v)])
# RAFT full original archive: diagnostic prior local file is truncated; require hash match.
raft=P/'RAFT_passage_complete.nc';assert hashlib.sha256(raft.read_bytes()).hexdigest()=='9355ddd9535f53e291437645a70995b0a66a93bdc6f3ddf44b655e057503d343'
d=xr.open_dataset(raft);print('RAFT',dict(d.sizes),flush=True)
fields={k:d[k].values for k in ('lat','lon','vmax','mslp','rmax')}
for i in range(d.sizes['storms']):
 la=fields['lat'][i];lo=fields['lon'][i];v=fields['vmax'][i];pc=fields['mslp'][i];rm=fields['rmax'][i]
 valid=np.isfinite(la)&np.isfinite(lo)&np.isfinite(v)&(v>0)&np.isfinite(pc)&(pc>0)&np.isfinite(rm)&(rm>0)
 ix=np.where(valid)[0]
 if len(ix)<2 or np.any(np.diff(ix)!=1):continue
 eligible['RAFT_valid']+=1
 if np.min(distance(la[ix],lo[ix]))>500:continue
 add('RAFT',i,'',la[ix],lo[ix],v[ix],pc[ix],rm[ix],ix)
 if i%10000==0:print('RAFT progress',i,len(rows),flush=True)
d.close()
# STORM v4 ten North Atlantic member files, each representing 1000 years.
zp=P/'STORMV4_passage.zip';assert hashlib.sha256(zp.read_bytes()).hexdigest()=='d36ad49b875e00db166e095b93eda2b245e1e0e2d959a173a42347cfa5355820'
with zipfile.ZipFile(zp) as z:
 paths=sorted((a for a in z.namelist() if '_NA_' in a),key=lambda a:int(a.rsplit('_',1)[-1].split('.')[0]));assert len(paths)==10
 for fi,name in enumerate(paths):
  with z.open(name) as f:a=np.loadtxt(f,delimiter=',',dtype=float)
  key=a[:,0].astype('int64')*100+a[:,2].astype('int64');starts=np.r_[0,1+np.where(np.diff(key)!=0)[0]];ends=np.r_[starts[1:],len(a)]
  for b,e in zip(starts,ends):
   c=a[b:e];valid=np.isfinite(c[:,5:10]).all(axis=1)&(c[:,7]>0)&(c[:,8]>0)&(c[:,9]>0)
   if len(c)<2 or not valid.all() or not np.all(np.diff(c[:,3])==1):continue
   eligible['STORM_valid']+=1
   if np.min(distance(c[:,5],c[:,6]-360))>500:continue
   identity=fi*1000000+int(c[0,0])*100+int(c[0,2]);v=c[:,8]*1.11/0.514444
   add('STORM',identity,int(c[0,0])+fi*1000,c[:,5],c[:,6]-360,v,c[:,7],c[:,9]/1.852,c[:,3])
  print('STORM progress',fi,len(rows),flush=True)
# HURDAT2 eligible storms = prior observational genesis proxy (TS/HU >=35, TD/TS/HU span >=24h).
eb={}
for line in open(P/'EBTRK_AL_1851_2021.txt'):
 t=line.split()
 if len(t)<18:continue
 try:
  y=int(t[3]);key=(t[0],f'{y:04d}{t[2]}')
  if 1988<=y<=2018:eb[key]=float(t[8])
 except (ValueError,IndexError):pass
lines=open(B/'hurdat2-1851-2025-092326.txt').readlines();k=0;observed=[]
while k<len(lines):
 h=[x.strip() for x in lines[k].split(',') if x.strip()];ident=h[0];n=int(h[2]);k+=1
 rec=[]
 for line in lines[k:k+n]:
  t=[s.strip() for s in line.split(',')];dt=datetime.strptime(t[0]+t[1],'%Y%m%d%H%M')
  try:la=float(t[4][:-1])*(1 if t[4][-1]=='N' else -1);lo=float(t[5][:-1])*(-1 if t[5][-1]=='W' else 1);v=float(t[6]);pc=float(t[7])
  except (ValueError,IndexError):continue
  rec.append((dt,t[3],la,lo,v,pc))
 k+=n;year=int(ident[4:]);
 if not 1979<=year<=2018:continue
 tropical=[r for r in rec if r[1] in ('TD','TS','HU')];ts=[r for r in rec if r[1] in ('TS','HU') and r[4]>=35]
 if not tropical or not ts or (tropical[-1][0]-tropical[0][0]).total_seconds()<86400:continue
 eligible['HURDAT2_'+str(year)]+=1
 if np.min(distance([r[2] for r in ts],[r[3] for r in ts]))>500:continue
 rm=[eb.get((ident,r[0].strftime('%Y%m%d%H')),np.nan) for r in ts]
 rm=np.array([v if v>0 else np.nan for v in rm])
 add('HURDAT2',ident,year,[r[2] for r in ts],[r[3] for r in ts],[r[4] for r in ts],[r[5] for r in ts],rm,[r[0].isoformat() for r in ts])
observed40=sum(eligible['HURDAT2_'+str(y)] for y in range(1979,2019));observed31=sum(eligible['HURDAT2_'+str(y)] for y in range(1988,2019));assert observed40==483,(observed40,observed31)
with open(P/'passage_events_v1.csv','x',newline='') as f:
 w=csv.writer(f);w.writerow(cols);w.writerows(rows)
print('events',len(rows),'eligible',dict(eligible),flush=True)
# Cumulative categories as threshold at passage, mutually exclusive bins also retained in events file.
thresholds={'TS':35,'Cat1+':64,'Cat3+':96,'Cat4-5':114}
periods=[('RAFT','all',40000,12.075),('RAFT','rate14.5',40000,14.5),('STORM','all',107063,None),('HURDAT2','1979-2018',observed40,observed40/40),('HURDAT2','1988-2018',observed31,observed31/31)]
# denominator is ALL original catalog storms, not only coast-near storms. STORM yearly counts use its native 10000 years.
out=[];bucket=collections.defaultdict(list)
for r in rows:bucket[(r[0],r[3],r[5])].append(r)
for source,period,denom,rate in periods:
 for s in ids:
  seg=next(x for x,v in segs.items() if s in v)
  for zone in RINGS:
   ev=[r for r in bucket[(source,s,zone)] if source!='HURDAT2' or (period=='1979-2018' or int(r[2])>=1988)]
   for label,cut in thresholds.items():
    selected=[r for r in ev if r[7]>=cut];n=len(selected)
    yearrate=n/10000 if source=='STORM' else n/denom*rate
    vv=[r[7] for r in selected];dp=[r[8] for r in selected if r[8]!='']
    q=lambda x,p:float(np.quantile(x,p)) if x else None
    out.append(dict(source=source,period=period,site=s,segment=seg,zone=zone,threshold=label,n=n,denominator=denom,per_1000=n/denom*1000,per_year=yearrate,v_p50=q(vv,.5),v_p90=q(vv,.9),v_p99=q(vv,.99),dp_n=len(dp),dp_p50=q(dp,.5),dp_p90=q(dp,.9),dp_p99=q(dp,.99)))
with open(P/'passage_station_v1.csv','x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
# Coast segment = unweighted average of constituent station values; not unique storms along coastline.
coast=[]
for src,per,den,rate in periods:
 for seg,ss in segs.items():
  for zone in RINGS:
   for label in thresholds:
    vals=[r for r in out if r['source']==src and r['period']==per and r['site'] in ss and r['zone']==zone and r['threshold']==label]
    coast.append(dict(source=src,period=per,segment=seg,sites=len(ss),zone=zone,threshold=label,mean_n=float(np.mean([r['n'] for r in vals])),mean_per_1000=float(np.mean([r['per_1000'] for r in vals])),mean_per_year=float(np.mean([r['per_year'] for r in vals]))))
with open(P/'passage_coast_v1.csv','x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(coast[0]));w.writeheader();w.writerows(coast)
# Paired year-block bootstrap for observation rates, exact yearly events, fixed sites, 2000 seeded resamples.
rng=np.random.default_rng(20261014);boots=[]
for period,ys in [('1979-2018',np.arange(1979,2019)),('1988-2018',np.arange(1988,2019))]:
 draws=rng.choice(ys,size=(2000,len(ys)),replace=True)
 for seg,ss in segs.items():
  for zone in RINGS:
   for label,cut in thresholds.items():
    counts=collections.Counter((int(r[2]),r[3]) for r in rows if r[0]=='HURDAT2' and r[5]==zone and r[7]>=cut and int(r[2]) in ys and r[3] in ss)
    yearly=np.array([sum(counts[(int(y),s)] for s in ss)/len(ss) for y in ys])
    samples=yearly[draws-ys[0]].mean(axis=1)
    boots.append(dict(period=period,segment=seg,zone=zone,threshold=label,mean_per_year=yearly.mean(),lo95=float(np.quantile(samples,.025)),hi95=float(np.quantile(samples,.975)),nonzero_years=int(np.count_nonzero(yearly)),years=len(ys)))
with open(P/'passage_obs_bootstrap_v1.csv','x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(boots[0]));w.writeheader();w.writerows(boots)
# Four segments, Cat3+ at 100 km: rate and conditional intensity plot.
fig,axs=plt.subplots(1,2,figsize=(12,4.8));xx=np.arange(4);width=.23
for j,(src,per) in enumerate([('RAFT','all'),('STORM','all'),('HURDAT2','1988-2018')]):
 yy=[next(r['mean_per_year'] for r in coast if (r['source'],r['period'],r['segment'],r['zone'],r['threshold'])==(src,per,seg,'km_le100','Cat3+')) for seg in segs]
 axs[0].bar(xx+(j-1)*width,yy,width,label=src)
 for i,seg in enumerate(segs):
  rr=[r for r in out if r['source']==src and r['period']==per and r['segment']==seg and r['zone']=='km_le100' and r['threshold']=='TS']
  # Conditional event-level p90 intensity across sites; sites may duplicate same storm, declared.
  vv=[r[7] for r in rows if r[0]==src and r[3] in segs[seg] and r[5]=='km_le100' and r[7]>=35 and (src!='HURDAT2' or int(r[2])>=1988)]
  axs[1].scatter(i+(j-1)*width,np.quantile(vv,.9) if vv else np.nan,marker='o')
axs[0].set_xticks(xx,list(segs),rotation=16);axs[0].set_ylabel('Cat3+ passages / site / year (<=100 km)');axs[0].legend();axs[1].set_xticks(xx,list(segs),rotation=16);axs[1].set_ylabel('Passage vmax p90 (kt), TS+ <=100 km')
fig.text(.5,.01,'Sources: RAFT Xu 2024; STORM v4 4TU; HURDAT2 NHC 2026; EBTRK CIRA. Native nodes, no hazard-model winds.',ha='center',fontsize=8)
fig.tight_layout(rect=(0,.04,1,1));fig.savefig(P/'passage_v1.png',dpi=170);plt.close(fig)
meta={'eligible':dict(eligible),'observed_1979_2018':observed40,'observed_1988_2018':observed31,'event_zone_rows':len(rows),'rmw_coverage_near300':{s:{'nodes':coverage[(s,'nodes_near300')],'rmw':coverage[(s,'rmw_near300')]} for s in ids},'source_hashes':{'RAFT':hashlib.sha256(raft.read_bytes()).hexdigest(),'STORM':hashlib.sha256(zp.read_bytes()).hexdigest()},'definition':'native node event-site-zone strongest TS/HU node; threshold cumulative; fixed km nested, RMW 1-3 exclusive; no interpolation'}
(P/'passage_meta_v1.json').write_text(json.dumps(meta,indent=2));print('DONE',json.dumps({'observed40':observed40,'observed31':observed31,'rows':len(rows)}),flush=True)
