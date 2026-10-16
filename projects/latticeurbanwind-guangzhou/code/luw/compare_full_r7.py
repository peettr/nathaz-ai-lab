"""R7 full comparison: two states, two offsets, low-speed subset."""
from pathlib import Path
import csv,json,statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
b=Path(__file__).parent;d=json.loads((b/'offset_samples_r7.json').read_text());rows=d['rows'];assert len(rows)==80
out={'quantity':'z=2m / input U(15.9m); vector magnitude vs sqrt(vector magnitude squared + 2*k_resolved)','uref_mps':d['uref'],'dx':d['dx'],'mask_fit':d['mask_fit'],'upstream':d['upstream'],'metrics':{},'note':'k from sampled resolved velocity second moments only; no subgrid contribution; instantaneous scalar mean not directly output'}
fig,axes=plt.subplots(2,2,figsize=(11,10),constrained_layout=True)
for axrow,(shift,title) in zip(axes,[('plus_dx','(+1,+1,0)m'),('no_offset','(0,0,0)m')]):
 out['metrics'][shift]={}
 for ax,obs in zip(axrow,('after','before')):
  out['metrics'][shift][obs]={};low=[p for p in rows if p['sample'][shift]['sim_ratio']<.10]
  for subset,part in (('all80',rows),('low_s_cfd',low)):
   out['metrics'][shift][obs][subset]={}
   for name,key in (('S_CFD','sim_ratio'),('S_exp','exp_ratio')):
    x=[p[obs] for p in part];y=[p['sample'][shift][key] for p in part]
    out['metrics'][shift][obs][subset][name]={'n':len(part),'ids':[p['id'] for p in part],'mae':statistics.mean(abs(a-b) for a,b in zip(x,y)) if part else None,'r':statistics.correlation(x,y) if len(part)>1 and len(set(x))>1 and len(set(y))>1 else None,'sim_mean':statistics.mean(y) if part else None,'obs_mean':statistics.mean(x) if part else None,'mean_ratio':statistics.mean(y)/statistics.mean(x) if part else None,'nonfluid_stencil_n':sum(p['sample'][shift]['fluid_corners']<8 for p in part)}
  for name,key,color in (('S_CFD','sim_ratio','tab:blue'),('S_exp','exp_ratio','tab:orange')):
   x=[p[obs] for p in rows];y=[p['sample'][shift][key] for p in rows];v=out['metrics'][shift][obs]['all80'][name]
   ax.scatter(x,y,label=f'{name}: MAE {v["mae"]:.3f}, r {v["r"]:.3f}',s=18,alpha=.65,color=color)
  ax.plot([0,1.7],[0,1.7],'k-',lw=.7);ax.set(xlim=(0,1.7),ylim=(0,1.7),xlabel=f'Wind tunnel {obs} W, scalar U/Uref',ylabel='LUW z=2m / Uref',title=title+' / '+obs);ax.legend(fontsize=9)
fig.savefig(b/'CaseE_W_scatter_r7.png',dpi=160)
with (b/'CaseE_W_points_full_r7.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['id','x','y','before','after','s_cfd_no','s_exp_no','k_no','fluid_no','s_cfd_shift','s_exp_shift','k_shift','fluid_shift'])
 for p in rows:
  a=p['sample']['no_offset'];c=p['sample']['plus_dx'];w.writerow([p['id'],*p['xls_xy'],p['before'],p['after'],a['sim_ratio'],a['exp_ratio'],a['tke_m2s2'],a['fluid_corners'],c['sim_ratio'],c['exp_ratio'],c['tke_m2s2'],c['fluid_corners']])
(b/'CaseE_W_metrics_full_r7.json').write_text(json.dumps(out,indent=2));print(json.dumps(out['metrics'],indent=2))
