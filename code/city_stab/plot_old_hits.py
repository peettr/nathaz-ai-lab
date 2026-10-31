"""Small read-only diagram of previous scan hits from native z<=21 flags."""
from pathlib import Path
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent
flags=np.load(R/'stage3_native_flags.npz')['flags']
fig,axes=plt.subplots(2,3,figsize=(9,6))
rows=[]
for row,(x,y,z) in enumerate([(133,143,1),(147,394,21)]):
 for j,dz in enumerate([-1,0,1]):
  ax=axes[row,j];zz=z+dz
  if zz>=flags.shape[0]:
   ax.text(.5,.5,'not in z<=21 export',ha='center',va='center');ax.set_xlim(0,3);ax.set_ylim(0,3)
   continue
  patch=flags[zz,y-1:y+2,x-1:x+2]&3
  ax.imshow(patch==1,cmap='gray_r',vmin=0,vmax=1)
  ax.set_xticks(range(3),range(x-1,x+2));ax.set_yticks(range(3),range(y-1,y+2));
  for iy in range(3):
   for ix in range(3):ax.text(ix,iy,'S' if patch[iy,ix]==1 else 'E' if patch[iy,ix]==2 else 'F',ha='center',va='center',color='red')
  rows.append((x,y,z,zz,int((patch==1).sum())))
  ax.set_title(f'old scan ({x},{y},{z}), z={zz}')
fig.tight_layout();fig.savefig(R/'nan_old_hits_native_flags.png',dpi=140)
print(rows)
