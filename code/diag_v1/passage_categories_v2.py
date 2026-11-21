"""Supplement v1 cumulative threshold table with mutually exclusive TS/Cat1-2."""
import csv,collections,pathlib,numpy as np
P=pathlib.Path(__file__).resolve().parent
rows=list(csv.DictReader(open(P/'passage_events_v1.csv')));sites=list(csv.DictReader(open(P/'sites_min.csv')))
ids=[s['site'] for s in sites];segs={'TX':ids[:3],'LA_to_Panhandle':ids[3:9],'FL_peninsula':ids[9:16],'Carolinas':ids[16:]}
periods=[('RAFT','all',40000,12.075),('RAFT','rate14.5',40000,14.5),('STORM','all',107063,None),('HURDAT2','1979-2018',483,483/40),('HURDAT2','1988-2018',408,408/31)]
zones=('RMW_le1','RMW_1to3','km_le50','km_le100');bins={'TS_only':(35,64),'Cat1-2':(64,96),'Cat3+':(96,float('inf')),'Cat4-5':(114,float('inf'))}
buckets=collections.defaultdict(list)
for r in rows:buckets[(r['source'],r['site'],r['zone'])].append(r)
out=[]
for src,per,den,rate in periods:
 for seg,ss in segs.items():
  for site in ss:
   for zone in zones:
    rec=buckets[(src,site,zone)]
    if src=='HURDAT2' and per=='1988-2018':rec=[r for r in rec if int(r['year'])>=1988]
    for label,(lo,hi) in bins.items():
     select=[r for r in rec if lo<=float(r['vmax_kt'])<hi];n=len(select)
     out.append(dict(source=src,period=per,segment=seg,site=site,zone=zone,category=label,n=n,denominator=den,per_1000=n/den*1000,per_year=n/10000 if src=='STORM' else n/den*rate))
with open(P/'passage_station_categories_v2.csv','x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
coast=[]
for src,per,den,rate in periods:
 for seg,ss in segs.items():
  for zone in zones:
   for label in bins:
    match=[r for r in out if (r['source'],r['period'],r['segment'],r['zone'],r['category'])==(src,per,seg,zone,label)]
    coast.append(dict(source=src,period=per,segment=seg,sites=len(ss),zone=zone,category=label,mean_count=sum(r['n'] for r in match)/len(ss),mean_per_1000=sum(r['per_1000'] for r in match)/len(ss),mean_per_year=sum(r['per_year'] for r in match)/len(ss)))
with open(P/'passage_coast_categories_v2.csv','x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(coast[0]));w.writeheader();w.writerows(coast)
# Year resampling, category-specific exact-bin rates (do not treat sites as independent years).
rng=np.random.default_rng(20261014);boots=[]
for per,ys in [('1979-2018',np.arange(1979,2019)),('1988-2018',np.arange(1988,2019))]:
 draw=rng.choice(len(ys),size=(3000,len(ys)),replace=True)
 for seg,ss in segs.items():
  for zone in zones:
   for label,(lo,hi) in bins.items():
    counter=collections.Counter((int(r['year']),r['site']) for r in rows if r['source']=='HURDAT2' and r['site'] in ss and r['zone']==zone and lo<=float(r['vmax_kt'])<hi and int(r['year']) in ys)
    annual=np.array([sum(counter[(int(y),s)] for s in ss)/len(ss) for y in ys]);samples=annual[draw].mean(axis=1)
    boots.append(dict(period=per,segment=seg,zone=zone,category=label,mean_per_year=float(annual.mean()),lo95=float(np.quantile(samples,.025)),hi95=float(np.quantile(samples,.975)),nonzero_years=int(np.count_nonzero(annual)),years=len(ys)))
with open(P/'passage_obs_bootstrap_categories_v2.csv','x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(boots[0]));w.writeheader();w.writerows(boots)
print('v2 category rows',len(out),len(coast),len(boots))
