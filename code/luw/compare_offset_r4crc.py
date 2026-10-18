"""Compare two fixed VTK-vs-STL translations, before and after wind tunnel."""
from pathlib import Path
import json,statistics,csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
b=Path(__file__).parent; data=json.loads((b/'offset_samples_r4crc.json').read_text());rows=data['rows'];assert len(rows)==80
out={'assumption':'xls XY=raw STL XY, same axes; PF=raw+(1010.50008,1000.60004,-0.10)m; cropped raw x300 y650; building state unknown','quantity':data['quantity'],'mask_fit':data['mask_fit'],'metrics':{}}
fig,axs=plt.subplots(2,2,figsize=(11,10),constrained_layout=True)
for axis,label in zip(axs,('no_offset','plus_dx')):
    out['metrics'][label]={}
    for ax,obskey in zip(axis,('before','after')):
        x=[p[obskey] for p in rows]; y=[p['sample'][label]['sim_ratio'] for p in rows]
        mae=statistics.mean(abs(a-b) for a,b in zip(x,y));r=statistics.correlation(x,y)
        sim_mean=statistics.mean(y);obs_mean=statistics.mean(x)
        out['metrics'][label][obskey]={'n':len(rows),'mae':mae,'r':r,'sim_mean':sim_mean,'obs_mean':obs_mean,'sim_over_obs_mean':sim_mean/obs_mean,'nonfluid_interpolation_points':sum(p['sample'][label]['fluid_corners']<8 for p in rows)}
        ax.scatter(x,y,s=19,alpha=.75);ax.plot([0,1.7],[0,1.7],color='k',lw=.7)
        ax.set(xlim=(0,1.7),ylim=(0,1.7),xlabel='Wind tunnel W: U(2m)/Uin(15.9m)',ylabel='LUW W: |mean u|(2m)/Uin(15.9m)',title=f'{label} / {obskey}: MAE={mae:.3f}, r={r:.3f}, mean ratio={sim_mean/obs_mean:.2f}')
fig.savefig(b/'CaseE_W_offset_scatter_r4crc.png',dpi=140)
with (b/'CaseE_W_offset_points_r4crc.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['id','xls_x','xls_y','before','after','sim_no_offset','sim_plus_dx','fluid_corners_no_offset','fluid_corners_plus_dx'])
    for p in rows:w.writerow([p['id'],*p['xls_xy'],p['before'],p['after'],p['sample']['no_offset']['sim_ratio'],p['sample']['plus_dx']['sim_ratio'],p['sample']['no_offset']['fluid_corners'],p['sample']['plus_dx']['fluid_corners']])
(b/'CaseE_W_offset_metrics_r4crc.json').write_text(json.dumps(out,indent=2));print(json.dumps(out['metrics'],indent=2))
