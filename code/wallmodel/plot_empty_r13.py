import json,matplotlib.pyplot as plt
from pathlib import Path
r=Path('/content/luw_wall_empty_r13');d=json.loads((r/'empty_profiles_fixed_r13.json').read_text());fig,axs=plt.subplots(1,2,figsize=(11,4.5),sharex=True)
for v,label in [('off','no model'),('on','model, wrong layer'),('onfixed','model, physical ground')]:
 for h in (2.,5.,15.9):
  rows=[a for a in d[v]['rows'] if a['z']==h];axs[0].plot([a['x'] for a in rows],[a['ratio'] for a in rows],label=f'{label} z={h:g} m');axs[1].plot([a['x'] for a in rows],[a['TI_isotropic'] for a in rows],label=f'{label} z={h:g} m')
axs[0].axhline(1,color='gray',lw=.6);axs[0].set_ylabel('mean |U| / inlet U(z)');axs[1].set_ylabel('sqrt(2k/3)/|mean U| (resolved only)')
for ax in axs:ax.set_xlabel('x from west inlet (m)');ax.grid(alpha=.3)
axs[1].legend(loc='upper center',bbox_to_anchor=(.5,-.25),ncol=3,fontsize=7);fig.suptitle('Internal LUW empty Case E, 500 x 64 x 270 m; not full momentum budget');fig.tight_layout();fig.savefig(r/'empty_profiles_r13.png',dpi=160,bbox_inches='tight')
print('PLOT_DONE',r/'empty_profiles_r13.png')
