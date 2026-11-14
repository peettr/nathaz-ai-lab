"""GEV L-moment sensitivity: constant (no-ERA5) baseline and SS, from existing gev_fits.json; disclosure only."""
import csv,json,numpy as np
fits=json.load(open('gev_fits.json'));L={r['station']:r for r in csv.DictReader(open('loso_results.csv'))}
G={r['station']:r for r in csv.DictReader(open('gev_lmom_sensitivity.csv'))}
out=[]
for st,r in L.items():
 tr=json.loads(r['train_stations']);row={'station':st,'region':r['region'],'n_train':len(tr)}
 for T in (10,50):
  obs=fits[st]['station'][f'x{T}'];base=np.mean([fits[q]['station'][f'x{T}'] for q in tr])
  row[f'R{T}']=float(G[st][f'R{T}']);row[f'R{T}_base']=base/obs
 out.append(row)
R=np.array([o['R10'] for o in out]);B=np.array([o['R10_base'] for o in out]);R5=np.array([o['R50'] for o in out]);B5=np.array([o['R50_base'] for o in out])
res={'n':len(out),'hit_gev':int((abs(R-1)<=.15).sum()),'hit_base':int((abs(B-1)<=.15).sum()),
 'SS10':float(1-np.mean(np.log(R)**2)/np.mean(np.log(B)**2)),
 'median_absR50_gev':float(np.median(abs(R5-1))),'median_absR50_base':float(np.median(abs(B5-1)))}
for reg in ('plains','other'):
 m=np.array([o['region']==reg for o in out]);res[reg]={'n':int(m.sum()),'hit_gev':int((abs(R[m]-1)<=.15).sum()),'hit_base':int((abs(B[m]-1)<=.15).sum()),'SS10':float(1-np.mean(np.log(R[m])**2)/np.mean(np.log(B[m])**2))}
rng=np.random.default_rng(20261016);ss=[]
for _ in range(2000):
 i=rng.integers(0,len(out),len(out));ss.append(1-np.mean(np.log(R[i])**2)/np.mean(np.log(B[i])**2))
res['SS10_ci90']=[float(np.percentile(ss,5)),float(np.percentile(ss,95))]
json.dump(res,open('gev_baseline_result.json','w'),indent=1)
with open('gev_baseline_rows.csv','w',newline='') as f:
 w=csv.DictWriter(f,list(out[0]));w.writeheader();w.writerows(out)
print(json.dumps(res))
