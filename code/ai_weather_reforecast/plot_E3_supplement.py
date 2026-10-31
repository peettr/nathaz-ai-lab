"""Plot preregistered E3 regional-max absolute errors by lead time."""
import json,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
p=Path('/content/ai_weather');r=json.loads((p/'metrics_E3_supp.json').read_text())
fig,ax=plt.subplots(1,3,figsize=(12,3.8),constrained_layout=True)
leads=[12,24,48,72,120]
for a,key in zip(ax,['MLCAPE','DCAPE','shear06']):
 ref=r['reference']['E3'][key]['max']
 for m in ('Pangu6','FuXi'):
  cs=[next(c for c in r['cases'] if c['model']==m and c['lead_h']==h) for h in leads]
  a.plot(leads,[c['judge']['absolute_error'][key] for c in cs],marker='o',label=m)
 a.plot(leads,[abs(r['baseline'][f'E3_P{24*((h+23)//24)}'][key]['max']-ref) for h in leads],marker='s',linestyle='--',color='k',label='P (ERA5 persistence)')
 a.set(xlabel='Lead time (h)',ylabel='Absolute regional-max error',title=f'E3 {key}');a.grid(alpha=.3)
ax[0].legend(fontsize=8);fig.savefig(p/'errors_E3_supp.png',dpi=160)
print('PLOT_COMPLETE',p/'errors_E3_supp.png')
