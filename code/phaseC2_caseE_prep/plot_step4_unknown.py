"""Plot unknown-link distribution from the native flags/STL audit, without changing data."""
from pathlib import Path
import json,numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent;s=json.loads((R/'step4_native_v2_stats.json').read_text())
fig,axes=plt.subplots(1,2,figsize=(12,4))
for k in ('ground','building','unknown'):
 axes[0].plot(range(91),s['z_hist'][k],label=k)
axes[0].set(xlabel='source z index',ylabel='fluid-to-solid links',xlim=(20,90));axes[0].legend()
a=np.asarray(s['unknown_xy_hist_25x25']);im=axes[1].imshow(a.T,origin='lower',extent=(0,500,0,500),cmap='magma');axes[1].set(xlabel='x index',ylabel='y index',title='unknown owner (all exported z)');fig.colorbar(im,ax=axes[1]);fig.tight_layout();fig.savefig(R/'step4_unknown_distribution.png',dpi=150)
print(R/'step4_unknown_distribution.png')
