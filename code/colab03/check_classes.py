import numpy as np,pathlib,os
p=pathlib.Path('/content/l264a100/texas')
for y,x in [(252,561),(0,810)]:
 a=np.load(p/'VGTYP.npy',mmap_mode='r')[y:y+440,x:x+408]
 print('CLASSES',y,x,list(zip(*[v.tolist() for v in np.unique(a,return_counts=True)])),flush=True)
q=pathlib.Path('/content/l264a100/fast_data')
print('FAST', (q/'fast.done').exists(),(q/'fast.failed').exists(),flush=True)
print('LOGTAIL', (q/'fast.log').read_text()[-750:] if (q/'fast.log').exists() else 'no log',flush=True)
print('SOURCE',pathlib.Path('/content/l264a100/AERO_ODE/AERO_Surface_WD/Hrrr_rb/data/roughness_log_z0_norm.npy').exists(),flush=True)
