"""Compute AIJ Case A section metrics and an auditable comparison figure."""
from pathlib import Path
import json,numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).parent
obj=json.loads((root/'samples_caseA.json').read_text())
refs={'z8':[.74,.62,.78,.26,.31,.64],'z80':[.93,.97,.92,.13,.90,.88],'vertical':[.81,.89,.97,.12,.90,.53]}
def metric(p,o,kp,ko):
    p=np.array(p);o=np.array(o);kp=np.array(kp);ko=np.array(ko)
    kvalid=np.abs(ko)>.05
    fac=lambda a,b:float(np.mean((a>=.5*b)&(a<=2*b)))
    corr=lambda a,b:float(np.corrcoef(a,b)[0,1])
    return {'n':len(p),'speed_fac2':fac(p,o),'q_relative25':float(np.mean(np.abs(p-o)<=.25*np.abs(o))),'q_absolute25':float(np.mean(np.abs(p-o)<=.25)),'speed_r':corr(p,o),'nrmse_obsmean':float(np.sqrt(np.mean((p-o)**2))/np.mean(o)),'nrmse_range':float(np.sqrt(np.mean((p-o)**2))/(max(o)-min(o))),'tke_fac2':fac(kp[kvalid],ko[kvalid]),'tke_r':corr(kp[kvalid],ko[kvalid]),'n_tke':int(sum(kvalid)),'speed_mean_ratio':float(np.mean(p)/np.mean(o))}
result={}
for label in ('plus_xy','no_shift'):
    result[label]={}
    for group,rows in obj['groups'].items():
        pred=[t[label]['speed'] for t in rows];obs=[t['obs_speed'] for t in rows];kp=[t[label]['k'] for t in rows];ko=[t['obs_k'] for t in rows]
        m=metric(pred,obs,kp,ko);m['mixed_solid']=sum(t[label]['fluid_corners']<8 for t in rows);m['paper']={'speed_fac2':refs[group][0],'q':refs[group][1],'speed_r':refs[group][2],'nrmse':refs[group][3],'tke_fac2':refs[group][4],'tke_r':refs[group][5]};result[label][group]=m
(root/'metrics_caseA.json').write_text(json.dumps({'source':obj['vtk'],'grid':obj['dimensions'],'origin':obj['origin'],'mask':obj['mask'],'metrics':result,'definition_note':'q relative 0.25 and absolute 0.25 both shown; paper does not define denominator or absolute floor. NRMSE alternatives mean/range. TKE is resolved sampled variance only.'},indent=2))
fig,axes=plt.subplots(2,3,figsize=(13,8))
for j,(key,title) in enumerate([('z8','z/H=0.125'),('z80','z/H=1.25'),('vertical','center vertical')]):
    rows=obj['groups'][key]
    for a,obskey,predkey,lim in [(axes[0,j],'obs_speed','speed',1.65),(axes[1,j],'obs_k','k',.3)]:
        x=[t[obskey] for t in rows];y=[t['plus_xy'][predkey] for t in rows];a.scatter(x,y,s=19,alpha=.75)
        a.plot([0,lim],[0,lim],'k--',lw=1);a.set_xlim(0,lim);a.set_ylim(0,lim);a.grid(alpha=.2);a.set_title(title)
        a.set_xlabel('wind tunnel '+('U/UH' if predkey=='speed' else 'k/UH²'));a.set_ylabel('LUW '+('U/UH' if predkey=='speed' else 'k/UH²'))
fig.tight_layout();fig.savefig(root/'CaseA_scatter_caseA.png',dpi=160)
print(json.dumps(result,indent=2))
