"""Compute western Case E metrics and scatter after CRC field extraction."""
from pathlib import Path
import json,csv,math,statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
b=Path(__file__).parent;d=json.loads((b/'samples_r4crc.json').read_text());rows=d['rows'];assert len(rows)==80
out={'assumption':d['registration'],'quantity':'magnitude of mean velocity interpolated to z=2m / profile.dat inflow U(15.9m)=3.9286416 m/s','grid_dx':d['dx'],'grid_dimensions':d['dimensions'],'upstream':d['upstream'],'metrics':{}}
with (b/'CaseE_W_points_r4crc.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['id','xls_x','xls_y','sim_ratio','before_ratio','after_ratio','fluid_corners'])
 for a in rows:w.writerow([a['id'],*a['xls_xy'],a['sim_ratio'],a['before'],a['after'],a['fluid_corners']])
fig,ax=plt.subplots(1,2,figsize=(12,5),constrained_layout=True)
for panel,key in zip(ax,['before','after']):
 sim=[a['sim_ratio'] for a in rows];obs=[a[key] for a in rows];mae=statistics.mean(abs(x-y) for x,y in zip(sim,obs));r=statistics.correlation(sim,obs);mu=statistics.mean(sim);mo=statistics.mean(obs)
 out['metrics'][key]={'n':80,'mae':mae,'r':r,'sim_mean':mu,'obs_mean':mo,'sim_over_obs_mean':mu/mo}
 panel.scatter(obs,sim,s=22,alpha=.75);panel.plot([0,1.7],[0,1.7],color='k',lw=.7);panel.set(xlim=(0,1.7),ylim=(0,1.7),xlabel='Wind tunnel W: U(2m)/Uin(15.9m)',ylabel='LUW W: |mean u|(2m)/Uin(15.9m)',title=f'{key}: MAE={mae:.3f}, r={r:.3f}, means={mu/mo:.2f}')
fig.savefig(b/'CaseE_W_scatter_r4crc.png',dpi=150)
(b/'CaseE_W_metrics_r4crc.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
