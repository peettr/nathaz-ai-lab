import csv,json,pathlib,numpy as np
from scipy.optimize import least_squares
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
r=pathlib.Path(__file__).parent
old=list(csv.DictReader(open(r.parent/'zenodo_inflow/compare_AIJ.csv')))
new=list(csv.DictReader(open(r/'profile_weighted.csv')))
b2=json.load(open(r.parents[1]/'wp1b_ibm/inflow_ti/B2_offset_samples.json'))['profiles']
heights=np.array([float(x['z_target_full_m']) for x in new]); U=np.array([float(x['Ustream_mps']) for x in new]); K=np.array([float(x['k_temporal_m2s2']) for x in new]);
zold=np.array([float(x['z_target_full_m']) for x in old]);uo=np.array([float(x['U_AIJ_mps']) for x in old]);ko=np.array([float(x['k_AIJ_m2s2']) for x in old]);
ref=float(np.interp(15.9,heights,U)); officialref=float(np.interp(15.9,zold,uo));
rows=[]
for h,u,k in zip(heights,U,K):
 if h>30:continue
 row={'z_m':h,'precursor_U_mps':u,'precursor_U_norm':u/ref,'precursor_k':k,'official_U_mps':float(np.interp(h,zold,uo)),'official_U_norm':float(np.interp(h,zold,uo)/officialref),'official_k':float(np.interp(h,zold,ko))}
 for x in [5,25,42]:
  p=[p for p in b2 if p['x']==x];zh=np.array([p['z_agl'] for p in p]);uu=np.array([p['U_mps'] for p in p]);
  row[f'B2_x{x}_U_norm']=float(np.interp(h,zh,uu)/3.9286416) if len(p) else None
 rows.append(row)
with open(r/'compare_e2.csv','w',newline='') as f:
 w=csv.DictWriter(f,rows[0].keys());w.writeheader();w.writerows(rows)
fits=[]
for upper in [5,10]:
 sel=(heights>=1.25)&(heights<=upper);z=heights[sel];y=U[sel]
 a,b=np.polyfit(np.log(z),y,1); pred=a*np.log(z)+b
 fits.append(dict(max_z=upper,n=len(z),u_star=float(.4*a),z0_m=float(np.exp(-b/a)),rmse_mps=float(np.sqrt(np.mean((pred-y)**2)))))
print('FIT',fits)
fig,axs=plt.subplots(1,2,figsize=(10,5))
for ax,key,oldkey,label in [(axs[0],U,'U_precursor_mps','U (m/s)'),(axs[1],K,'k_precursor_resolved_m2s2','k (m2/s2)')]:
 ax.plot(key,heights,'o-',label='E2 10-30s weighted')
 ax.plot(np.array([float(x[oldkey]) for x in old]),zold,'--',label='old 0-30s equal')
 ax.plot(uo if ax is axs[0] else ko,zold,':',label='AIJ Inflow')
 ax.set_ylim(0,30);ax.set_xlabel(label);ax.set_ylabel('z full scale (m)');ax.grid();ax.legend()
fig.tight_layout();fig.savefig(r/'compare_e2.png',dpi=150)
json.dump(dict(fits=fits,ref_precursor_mps=ref,ref_official_mps=officialref,rows=len(rows)),open(r/'analysis_meta.json','w'),indent=2)
