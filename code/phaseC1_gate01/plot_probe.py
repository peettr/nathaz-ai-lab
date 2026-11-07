"""Plot read-only GPU address-probe traces (not a LUW gate result)."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path(__file__).resolve().parent
fig, axs=plt.subplots(2,2,figsize=(10,7),constrained_layout=True)
for axrow,filename,title in zip(axs,('probe_impulse_v2.csv','probe_force_v2.csv'),('Initial shear release','Constant force 2e-6')):
    rows=list(csv.DictReader((p/filename).open()))
    rows=[r for r in rows if int(r['step'])<=20]
    t=[int(r['step']) for r in rows]
    for ax,layer in zip(axrow,('y1','y2')):
        for col,label in ((f'native_{layer}','Native address emulation'),(f'explicit_{layer}','Explicit halfway BB')):
            ax.plot(t,[float(r[col]) for r in rows],marker='.' if layer=='y1' else None,label=label)
        ax.set(title=f'{title} / {layer}',xlabel='step',ylabel='u_x (lattice)')
        ax.legend(fontsize=8)
fig.suptitle('Standalone CUDA address probe; NOT a FluidX3D gate test')
fig.savefig(p/'transient_address_probe.png',dpi=150)
print(p/'transient_address_probe.png')
