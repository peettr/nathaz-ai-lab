import csv,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path(__file__).parent
out={}
fig,axes=plt.subplots(2,2,figsize=(10,7))
for row,kind in enumerate(('couette','poiseuille')):
 a=[r for r in csv.DictReader((p/f'new_type_s_{kind}.csv').open()) if r['step'].isdigit()]
 b=[r for r in csv.DictReader((p/f'new_ibb_{kind}.csv').open()) if r['step'].isdigit()]
 assert [x['step'] for x in a]==[x['step'] for x in b]
 t=np.array([int(x['step']) for x in a]);out[kind]={}
 for col,ax in zip(('ux1','px'),axes[row]):
  aa=np.array([float(x[col]) for x in a]);bb=np.array([float(x[col]) for x in b]);d=np.abs(aa-bb)
  out[kind][col]={'max_abs':float(d.max()),'at_step':int(t[d.argmax()]),'final_abs':float(d[-1]),'first20_max_abs':float(d[t<=20].max())}
  ax.plot(t,aa,label='TYPE_S');ax.plot(t,bb,'--',label='LINK_IBB q=0.5');ax.set(title=kind+' '+col,xlabel='step',ylabel=col);ax.legend()
 for col in ('ux2','mass'):
  aa=np.array([float(x[col]) for x in a]);bb=np.array([float(x[col]) for x in b]);d=np.abs(aa-bb)
  out[kind][col]={'max_abs':float(d.max()),'at_step':int(t[d.argmax()]),'final_abs':float(d[-1]),'first20_max_abs':float(d[t<=20].max())}
 # Lag search uses first 20 sampled steps, neither exact nor a proof of time parity.
 for col in ('ux1','px'):
  aa=np.array([float(x[col]) for x in a]);bb=np.array([float(x[col]) for x in b]);out[kind][col]['lag_rmse']={str(lag):float(np.sqrt(np.mean((aa[max(0,lag):min(20,20+lag)]-bb[max(0,-lag):min(20,20-lag)])**2))) for lag in (-1,0,1)}
fig.tight_layout();fig.savefig(p/'ibb_transient_compare.png',dpi=160)
(p/'ibb_comparison_metrics.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
