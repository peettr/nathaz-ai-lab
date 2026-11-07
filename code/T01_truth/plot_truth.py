import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parent
truth=json.loads((root/'truth.json').read_text())
t=np.arange(601)
fig,ax=plt.subplots(figsize=(9,4.8))
for key,label,col in [('template','Template steady optimum','#1765a3'),('steady_U30','U=30 steady optimum','#e2821e'),('event_opt','Event peak optimum','#449359')]:
    r=truth['cases'][key]; ax.plot(t,r['q_var'],label=label,color=col)
    ax.fill_between(t,*r['q_ci'],alpha=.15,color=col)
ax.set(xlabel='Time (s)',ylabel=r'Tower displacement variance $\sigma_q^2$ (m$^2$)',title='L22.6 T01 | CRC Monte Carlo; N=2000; input: T01 template')
ax.legend();fig.tight_layout();fig.savefig(root/'q_variance.png',dpi=170);plt.close(fig)
rows=[json.loads(line) for line in (root/'grid.jsonl').read_text().splitlines()]
fig,ax=plt.subplots(figsize=(7,5.5)); nu=np.array([r['nu'] for r in rows]); zd=np.array([r['zeta_d'] for r in rows]); val=np.array([r['peak_var'] for r in rows]); best=truth['optimization']['optimum'];
scatter=ax.scatter(nu,zd,c=val/best['peak_var'],cmap='viridis',s=36)
ax.scatter([best['nu']],[best['zeta_d']],marker='*',s=170,c='red',edgecolor='black',label='best sampled MC point')
fig.colorbar(scatter,ax=ax,label='MC event peak variance / sampled minimum')
ax.set(xlabel=r'Frequency ratio $\nu$',ylabel=r'Damping ratio $\zeta_d$',title='L22.6 T01 | CRC Monte Carlo objective surface; template input')
ax.legend(loc='best');fig.tight_layout();fig.savefig(root/'objective_surface.png',dpi=170)
