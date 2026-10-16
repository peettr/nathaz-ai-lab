import json
from pathlib import Path
import matplotlib.pyplot as plt
r=Path(__file__).resolve().parent/'cont4_outputs'
colors={'off':'#525252','on_first_fix':'#147d9d','on_second_fix':'#c1552a'}
labels={'off':'no model','on_first_fix':'wall stress at first cell','on_second_fix':'wall stress from second cell'}
fig,axs=plt.subplots(1,2,figsize=(11,4))
for variant in colors:
 d=json.loads((r/f'{variant}_profile.json').read_text())
 for h,style in [(2.,'-'),(15.9,'--')]:
  rows=[v for v in d['rows'] if v['z']==h]
  axs[0].plot([v['x'] for v in rows],[v['ratio'] for v in rows],style,color=colors[variant],label=labels[variant]+f' z={h:g}m')
 rows=[v for v in d['rows'] if v['z']==2.]
 axs[1].plot([v['x'] for v in rows],[v['TI'] for v in rows],'-o',markersize=2,color=colors[variant],label=labels[variant])
for ax in axs:ax.set_xlabel('Distance from west inlet (m)');ax.grid(alpha=.3)
axs[0].set_ylabel('Mean speed / prescribed inlet speed');axs[0].axhspan(.85,1.05,alpha=.08,color='green');axs[0].legend(fontsize=7)
axs[1].set_ylabel('Resolved isotropic TI proxy at z=2m');axs[1].legend(fontsize=8)
fig.tight_layout();fig.savefig(r/'empty_profiles_cont4.png',dpi=175)
for v in colors:
 d=json.loads((r/f'{v}_profile.json').read_text());print(v,[(a['x'],round(a['ratio'],4),round(a['TI'],4)) for a in d['rows'] if a['z']==2 and a['x'] in (200,300,400)])
