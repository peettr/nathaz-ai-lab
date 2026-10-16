"""Independent Case A metrics and inflow decay comparison."""
from pathlib import Path
import json, math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
r=Path(__file__).parent
new=json.loads((r/'samples_caseA_turb.json').read_text())
old=json.loads((r/'samples_caseA_zcheck.json').read_text())
ref=json.loads((r/'metrics_caseA_final.json').read_text())
def metric(rows):
    a=np.array([v['plus_xyz']['speed'] for v in rows]); b=np.array([v['obs_speed'] for v in rows]);
    ak=np.array([v['plus_xyz']['k'] for v in rows]); bk=np.array([v['obs_k'] for v in rows]); keep=np.abs(bk)>.05
    corr=lambda x,y:float(np.corrcoef(x,y)[0,1])
    fac=lambda x,y:float(np.mean((x>=.5*y)&(x<=2*y)))
    rmse=float(np.sqrt(np.mean((a-b)**2)))
    return dict(n=len(a),n_tke=int(keep.sum()),FAC2=fac(a,b),q_abs025=float(np.mean(abs(a-b)<=.25)),q_rel025=float(np.mean(abs(a-b)<=.25*abs(b))),r=corr(a,b),NRMSE_range=rmse/float(np.ptp(b)),NRMSE_mean=rmse/float(np.mean(b)),TKE_FAC2=fac(ak[keep],bk[keep]),TKE_r=corr(ak[keep],bk[keep]),mean_ratio=float(a.mean()/b.mean()),mixed_solid=sum(v['plus_xyz']['fluid_corners']<8 for v in rows))
out={'definition':'Same Case A official 4m,40m,vertical; +2,+2,+2m geometry shift; q abs ±.25 and NRMSE/range assumed; alternative q relative ±25% and NRMSE/mean','paper':ref['paper'],'baseline':{},'turb':{},'delta_new_minus_baseline':{},'upstream':new['upstream'],'mask':new['mask']}
for g in ('z8','z80','vertical'):
    base=metric(old['groups'][g]); newmet=metric(new['groups'][g]);out['baseline'][g]=base;out['turb'][g]=newmet
    out['delta_new_minus_baseline'][g]={k:newmet[k]-base[k] for k in ('FAC2','q_abs025','r','NRMSE_range','TKE_FAC2','TKE_r','mean_ratio')}
(r/'metrics_caseA_turb.json').write_text(json.dumps(out,indent=2))
fig,ax=plt.subplots(2,3,figsize=(13,8))
for j,(g,label) in enumerate((('z8','z/B=.125, 4 m'),('z80','z/B=1.25, 40 m'),('vertical','center vertical'))):
    for i,(ob,k,lim,title) in enumerate((('obs_speed','speed',1.7,'U/UH'),('obs_k','k',.4,'k/UH²'))):
        p=ax[i,j];s=new['groups'][g];o=old['groups'][g];p.scatter([v[ob] for v in o],[v['plus_xyz'][k] for v in o],s=15,alpha=.5,label='baseline');p.scatter([v[ob] for v in s],[v['plus_xyz'][k] for v in s],s=15,alpha=.5,label='turb');p.plot([0,lim],[0,lim],'k--');p.set(xlim=(0,lim),ylim=(0,lim),xlabel='AIJ '+title,ylabel='LUW '+title,title=label);p.grid(alpha=.2)
ax[0,0].legend();fig.tight_layout();fig.savefig(r/'CaseA_scatter_caseA_turb.png',dpi=160)
fig,ax=plt.subplots(figsize=(8,5))
for z in (4.,40.,64.,128.):
    q=[v for v in new['upstream'] if v['z_m']==z]
    ax.plot([v['x_from_inlet_m'] for v in q],[v['sample']['k'] for v in q],marker='o',label=f'z={z:g} m')
ax.set(xlabel='distance from west inlet (m)',ylabel='resolved k / UH²',title='LUW upstream mean-field turbulence');ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(r/'CaseA_upstream_k_caseA_turb.png',dpi=160)
for g in ('z8','z80','vertical'):print(g,'new',out['turb'][g],'delta',out['delta_new_minus_baseline'][g])
