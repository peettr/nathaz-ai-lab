import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path(__file__).resolve().parent
d=json.loads((p/'truth_C2.json').read_text())
t=np.arange(601)
fig,axs=plt.subplots(2,1,figsize=(9,8),sharex=True)
for ax,key,label,q in [(axs[0],'C1_template','C1 tau=60 s','C1'),(axs[1],'C2_template','C2 tau=10 s','C2')]:
 r=d['cases'][key]
 ax.plot(t,r['q_var'],label=label+' MC N=60000')
 ax.fill_between(t,*r['q_ci'],alpha=.25,label='pointwise bootstrap 95%')
 ax.plot(t,d['quasistatic_Q'][q],'--',label='Q stationary Lyapunov shortcut')
 ax.set_ylabel('Var(q) [m²]');ax.legend(fontsize=8)
axs[1].set_xlabel('t [s]')
fig.suptitle('Source: L22.6 T01 template, CRC Monte Carlo / quasi-steady Q')
fig.tight_layout();fig.savefig(p/'C1_C2_q_variance.png',dpi=150);plt.close(fig)
rows=[json.loads(x) for x in (p/'grid_C2.jsonl').read_text().splitlines()]
fig,ax=plt.subplots(figsize=(8,5)); sc=ax.scatter([r['nu'] for r in rows],[r['zeta_d'] for r in rows],c=[r['peak_var'] for r in rows],cmap='viridis');fig.colorbar(sc,label='max 1-s Var(q) [m²]')
ax.set(xlabel='nu',ylabel='zeta_d',title='C2 20k search; source: L22.6 T01 template + CRC MC')
fig.tight_layout();fig.savefig(p/'C2_objective_surface.png',dpi=150)
