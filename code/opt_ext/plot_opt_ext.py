import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path(__file__).resolve().parent
d=json.loads((p/'opt_ext.json').read_text())
g=d['grid']; nus=sorted(set(x['nu'] for x in g)); zs=sorted(set(x['zeta_d'] for x in g))
a=np.full((len(zs),len(nus)),np.nan)
for r in g:a[zs.index(r['zeta_d']),nus.index(r['nu'])]=r['peak_var']
fig,ax=plt.subplots(figsize=(8,5)); im=ax.pcolormesh(nus,zs,a,shading='nearest',cmap='viridis'); fig.colorbar(im,ax=ax,label='Peak q variance (m²), N=20000')
b=d['final_grid_best'];ax.plot(b['nu'],b['zeta_d'],'r*',ms=13);ax.set(xlabel='ν',ylabel='ζd',title='C2 extended objective grid | source: T01 template + CRC MC')
fig.tight_layout();fig.savefig(p/'objective_ext.png',dpi=180)
