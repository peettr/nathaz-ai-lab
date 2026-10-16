"""Compare completed official-plane Case A samples with AIJ and Han Table 2."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).parent
src=json.loads((root/'samples_caseA_officialrun.json').read_text())
obs=json.loads((root/'caseA_observations_official.json').read_text())
refs={'z8':[.74,.62,.78,.26,.31,.64],'z80':[.93,.97,.92,.13,.90,.88],'vertical':[.81,.89,.97,.12,.90,.53]}
def metric(rows,shift):
    p=np.array([r[shift]['speed'] for r in rows]); o=np.array([r['obs_speed'] for r in rows]);
    kp=np.array([r[shift]['k'] for r in rows]); ko=np.array([r['obs_k'] for r in rows]);
    valid=np.abs(ko)>.05
    fac=lambda a,b:float(np.mean((a>=.5*b)&(a<=2*b)))
    corr=lambda a,b:float(np.corrcoef(a,b)[0,1]) if len(a)>2 and np.std(a)>0 and np.std(b)>0 else None
    rmse=float(np.sqrt(np.mean((p-o)**2)))
    # q and NRMSE definition unspecified in Han; give both alternatives.
    return dict(n=len(p),n_tke=int(sum(valid)),speed_fac2=fac(p,o),q_relative25=float(np.mean(np.abs(p-o)<=.25*np.abs(o))),q_absolute25=float(np.mean(np.abs(p-o)<=.25)),speed_r=corr(p,o),nrmse_obsmean=rmse/float(np.mean(o)),nrmse_range=rmse/float(np.ptp(o)),tke_fac2=fac(kp[valid],ko[valid]),tke_r=corr(kp[valid],ko[valid]),speed_mean_ratio=float(np.mean(p)/np.mean(o)),mixed_solid=int(sum(r[shift]['fluid_corners']<8 for r in rows)))
result={}
for shift in ('plus_xy','no_shift'):
    result[shift]={}
    for key,rows in src['groups'].items():
        result[shift][key]={**metric(rows,shift),'paper':dict(zip(('speed_fac2','q','speed_r','nrmse','tke_fac2','tke_r'),refs[key]))}
    result[shift]['alternate_paper_zH']={}
    for key,alts in src['alternate_paper_zH'].items():
        merged=[{**r,shift:a[shift]} for r,a in zip(src['groups'][key],alts)]
        result[shift]['alternate_paper_zH'][key]=metric(merged,shift)
# Inspect volumetric mask overlap by height; offsets chosen by geometry rather than metrics.
mask={}
for z in (4,8,32,40,62,64,66,80):
    candidates=[r for r in src['mask'] if r['z']==z]
    mask[str(z)]=sorted(candidates,key=lambda r:r['iou'] if r['iou'] is not None else -1,reverse=True)
out={'source':src['vtk'],'grid':src['dimensions'],'origin':src['origin'],'spacing':src['spacing'],'mask_by_height':mask,'groups':result,'assumptions':'AIJ official planes 4/40 m; Han z/H judged typo by Lead. U=norm of mean velocity, k resolved variance only. q relative versus absolute .25, NRMSE observed mean versus observed range as sensitivity.'}
(root/'metrics_caseA_officialrun.json').write_text(json.dumps(out,indent=2))
fig,axes=plt.subplots(2,3,figsize=(13,8))
for j,(key,title) in enumerate([('z8','z/B=.125, z=4 m'),('z80','z/B=1.25, z=40 m'),('vertical','center vertical')]):
    rows=src['groups'][key]
    for ax,ok,pk,lim in [(axes[0,j],'obs_speed','speed',1.7),(axes[1,j],'obs_k','k',.4)]:
        x=[r[ok] for r in rows]; y=[r['plus_xy'][pk] for r in rows]
        ax.scatter(x,y,s=20,alpha=.7);ax.plot([0,lim],[0,lim],'k--',lw=1)
        ax.set(xlim=(0,lim),ylim=(0,lim),title=title,xlabel='AIJ '+('U/UH' if pk=='speed' else 'k/UH²'),ylabel='LUW '+('U/UH' if pk=='speed' else 'k/UH²'))
        ax.grid(alpha=.2)
fig.tight_layout();fig.savefig(root/'CaseA_scatter_officialrun.png',dpi=160)
for key in ('z8','z80','vertical'):
    print(key,'official',result['plus_xy'][key]);print(key,'unshifted',result['no_shift'][key])
print('mask z62',mask['62'][:4]);print('mask z64',mask['64'][:4]);print('mask z66',mask['66'][:4])
