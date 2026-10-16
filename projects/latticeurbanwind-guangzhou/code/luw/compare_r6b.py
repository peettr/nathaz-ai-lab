"""80-point W comparison: both states and registration hypotheses."""
from pathlib import Path
import json,statistics,csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
b=Path(__file__).parent;d=json.loads((b/'offset_samples_r6b.json').read_text());rows=d['rows'];assert len(rows)==80
out={'quantity':d['quantity'],'assumptions':'xls XY=raw STL XY, PF=raw+(1010.50008,1000.60004,-0.10)m; crop PF x300..1260 y750..1250; 0/+dx denotes VTK relative STL xyz shift; |mean vector| vs hot-wire scalar speed','uref_mps':d['uref'],'dx_m':d['dx'],'dimensions':d['dimensions'],'vtk_origin':d['origin'],'mask_fit':d['mask_fit'],'upstream':d['upstream'],'metrics':{}}
fig,axs=plt.subplots(2,2,figsize=(11,15),constrained_layout=True)
for axis,label in zip(axs,('no_offset','plus_dx')):
 out['metrics'][label]={}
 for ax,obskey in zip(axis,('after','before')):
  x=[p[obskey] for p in rows];y=[p['sample'][label]['sim_ratio'] for p in rows]
  mae=statistics.mean(abs(a-b) for a,b in zip(x,y));corr=statistics.correlation(x,y);ms=statistics.mean(y);mo=statistics.mean(x)
  out['metrics'][label][obskey]={'n':len(rows),'mae':mae,'r':corr,'sim_mean':ms,'obs_mean':mo,'sim_over_obs_mean':ms/mo,'nonfluid_stencil_points':sum(p['sample'][label]['fluid_corners']<8 for p in rows)}
  ax.scatter(x,y,s=19,alpha=.75);ax.plot([0,1.7],[0,1.7],color='k',lw=.7)
  ax.set(xlim=(0,1.7),ylim=(0,1.7),xlabel='Wind tunnel W: U(2m)/Uin(15.9m)',ylabel='LUW W: |mean u|(2m)/Uin(15.9m)',title=f'{label} / {obskey}: MAE={mae:.3f}, r={corr:.3f}, mean ratio={ms/mo:.2f}')
fig.savefig(b/'CaseE_W_scatter_r6b.png',dpi=150)
with (b/'CaseE_W_points_r6b.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['id','xls_x','xls_y','before','after','sim_no_offset','sim_plus_dx','fluid_corners_no_offset','fluid_corners_plus_dx'])
 for p in rows:w.writerow([p['id'],*p['xls_xy'],p['before'],p['after'],p['sample']['no_offset']['sim_ratio'],p['sample']['plus_dx']['sim_ratio'],p['sample']['no_offset']['fluid_corners'],p['sample']['plus_dx']['fluid_corners'],])
(b/'CaseE_W_metrics_r6b.json').write_text(json.dumps(out,indent=2));print(json.dumps(out['metrics'],indent=2))
