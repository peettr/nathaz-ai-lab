import csv,math,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
r=Path('./24_Urban_Wind_LBM/06_Logs/method_study/zenodo_inflow')
raw=list(csv.DictReader(open(r/'profile_binned.csv')))
off=[(1.25,.365,.008),(2.5,.390,.009),(5,.418,.009),(7.5,.437,.009),(12.5,.483,.010),(25,.559,.010),(50,.655,.009),(75,.730,.008),(100,.790,.007),(150,.893,.006),(200,.948,.004),(250,1,.002)]
def interp(h,j):
 if h<=off[0][0]:return off[0][j]
 for a,b in zip(off,off[1:]):
  if a[0]<=h<=b[0]:return a[j]+(b[j]-a[j])*(h-a[0])/(b[0]-a[0])
 return off[-1][j]
rows=[]
for a in raw:
 h=float(a['z_full_m']);u=float(a['Ustream_mps']);k=float(a['k_temporal_m2s2']);uo=7.8*interp(h,1);ko=7.8**2*interp(h,2)
 rows.append(dict(z_target_full_m=h,z_actual_mean_full_m=float(a['z_actual_mean_m']),n=int(a['n']),U_precursor_mps=u,U_AIJ_mps=uo,U_diff_pct=100*(u/uo-1),k_precursor_resolved_m2s2=k,k_AIJ_m2s2=ko,k_diff_pct=100*(k/ko-1)))
with open(r/'compare_AIJ.csv','w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
fig,(ax,bx)=plt.subplots(1,2,figsize=(10,6),sharey=True)
ys=[a['z_target_full_m'] for a in rows]
for panel,us,obs,label in [(ax,[a['U_precursor_mps'] for a in rows],[a['U_AIJ_mps'] for a in rows],'U (m/s)'),(bx,[a['k_precursor_resolved_m2s2'] for a in rows],[a['k_AIJ_m2s2'] for a in rows],'k (m²/s²)')]:
 panel.plot(us,ys,'o-',label='Zenodo 301 frames, ±1.25 m bin');panel.plot(obs,ys,'s--',label='AIJ Inflow (interpolated)');panel.set_xlabel(label);panel.grid(alpha=.3)
ax.set_ylabel('z full-scale equivalent (m)');ax.legend(fontsize=8);bx.legend(fontsize=8)
fig.suptitle('Case E precursor plane vs AIJ: unscaled speeds; k resolved only')
fig.tight_layout();fig.savefig(r/'compare_AIJ.png',dpi=150)
for a in rows:print(a)
