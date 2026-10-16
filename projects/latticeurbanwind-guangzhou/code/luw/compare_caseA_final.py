"""Final geometry-aligned and unshifted Case A metrics, no edits to solver."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
r=Path(__file__).parent; d=json.loads((r/'samples_caseA_zcheck.json').read_text())
ref={'z8':(.74,.62,.78,.26,.31,.64),'z80':(.93,.97,.92,.13,.90,.88),'vertical':(.81,.89,.97,.12,.90,.53)}
def calc(rows,shift):
    a=np.array([v[shift]['speed'] for v in rows]);b=np.array([v['obs_speed'] for v in rows]);ka=np.array([v[shift]['k'] for v in rows]);kb=np.array([v['obs_k'] for v in rows]);q=abs(kb)>.05
    fac=lambda x,y: float(np.mean((x>=.5*y)&(x<=2*y)))
    corr=lambda x,y: float(np.corrcoef(x,y)[0,1])
    rmse=np.sqrt(np.mean((a-b)**2))
    return dict(n=len(a),n_tke=int(q.sum()),FAC2=fac(a,b),q_abs025=float(np.mean(abs(a-b)<=.25)),q_rel025=float(np.mean(abs(a-b)<=.25*abs(b))),r=corr(a,b),NRMSE_range=float(rmse/np.ptp(b)),NRMSE_mean=float(rmse/np.mean(b)),TKE_FAC2=fac(ka[q],kb[q]),TKE_r=corr(ka[q],kb[q]),mean_ratio=float(np.mean(a)/np.mean(b)),mixed_solid=int(sum(v[shift]['fluid_corners']<8 for v in rows)))
out={'metadata':{'UH':d['UH'],'grid':d['dimensions'],'vtk_grid':d['dimensions'],'origin':d['origin'],'dx':d['spacing'],'field':d['vtk'],'official_planes':'z/B=.125=4m and 1.25=40m; Han z/H regarded typo by Lead','q_and_NRMSE':'q_abs025 and NRMSE_range used in displayed table as assumptions; alternatives supplied','k':'resolved velocity variance only, no SGS'},'paper':{g:dict(zip(('FAC2','q','r','NRMSE','TKE_FAC2','TKE_r'),v)) for g,v in ref.items()},'by_shift':{},'mask':d['mask']}
for shift in ('plus_xyz','plus_xy','no_shift'):
    out['by_shift'][shift]={g:calc(rows,shift) for g,rows in d['groups'].items()}
    if shift!='plus_xyz':
        out['by_shift'][shift]['alternative_heights']={g:calc([{**row,shift:alt[shift]} for row,alt in zip(d['groups'][g],ar)],shift) for g,ar in d['alternate_paper_zH'].items()}
(r/'metrics_caseA_final.json').write_text(json.dumps(out,indent=2))
fig,ax=plt.subplots(2,3,figsize=(13,8))
for j,(g,t) in enumerate((('z8','z/B=.125 (4 m)'),('z80','z/B=1.25 (40 m)'),('vertical','center vertical'))):
    rows=d['groups'][g]
    for i,(ok,pk,limit,label) in enumerate((('obs_speed','speed',1.7,'U/UH'),('obs_k','k',.4,'k/UH²'))):
        a=ax[i,j];a.scatter([v[ok] for v in rows],[v['plus_xyz'][pk] for v in rows],alpha=.7,s=20)
        a.plot([0,limit],[0,limit],'k--');a.set(xlim=(0,limit),ylim=(0,limit),title=t,xlabel='AIJ '+label,ylabel='LUW '+label);a.grid(alpha=.2)
fig.tight_layout();fig.savefig(r/'CaseA_scatter_final.png',dpi=160)
for g in ('z8','z80','vertical'):
 print(g,'paper',out['paper'][g]);print(g,'mask xyz',out['by_shift']['plus_xyz'][g]);print(g,'unshifted',out['by_shift']['no_shift'][g])
