"""Aligned r5/r6 scatter: same observation and (+1,+1,0)m VTK shift."""
from pathlib import Path
import csv,json,statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path(__file__).parent
r5=list(csv.DictReader((p/'CaseE_W_points_r5.csv').open()))
r6=list(csv.DictReader((p/'CaseE_W_points_r6b.csv').open()))
assert len(r5)==len(r6)==80
assert all(a['id']==b['id'] and a['after']==b['after'] and a['before']==b['before'] for a,b in zip(r5,r6))
fig,axs=plt.subplots(1,2,figsize=(12,5),constrained_layout=True)
for ax,field in zip(axs,('after','before')):
 obs=[float(q[field]) for q in r5]
 for rows,key,label,color in ((r5,'sim_best_xy_plus_dx_z0','r5 / 49m','tab:blue'),(r6,'sim_plus_dx','r6b / 509m','tab:orange')):
  sim=[float(q[key]) for q in rows]
  mae=statistics.mean(abs(a-b) for a,b in zip(obs,sim))
  ax.scatter(obs,sim,label=f'{label}: MAE={mae:.3f}',alpha=.6,s=23,color=color)
 ax.plot([0,1.7],[0,1.7],color='k',lw=.8)
 ax.set(title=field.capitalize()+' Construction (W)',xlim=(0,1.7),ylim=(0,1.7),xlabel='Wind tunnel U(2m)/Uin(15.9m)',ylabel='LUW |mean vector|(2m)/Uin(15.9m)')
 ax.legend(loc='upper left')
fig.savefig(p/'CaseE_W_scatter_compare_r5_r6b.png',dpi=160)
m5=json.loads((p/'CaseE_W_metrics_r5.json').read_text())
m6=json.loads((p/'CaseE_W_metrics_r6b.json').read_text())
for state in ('after','before'):
 old=m5['metrics']['best_xy_plus_dx_z0'][state]
 new=m6['metrics']['plus_dx'][state]
 print(state,'old_mae',old['mae'],'new_mae',new['mae'],'delta_mae',new['mae']-old['mae'],'old_r',old['r'],'new_r',new['r'],'old_ratio',old['sim_over_obs_mean'],'new_ratio',new['sim_over_obs_mean'])
