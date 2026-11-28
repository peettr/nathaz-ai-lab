#!/usr/bin/env python3
"""Synthetic solver used ONLY to exercise real worker/analysis/handoff paths."""
import csv,os,pathlib,numpy as np
D=pathlib.Path(os.environ['T17_B_DIR']);D.mkdir(exist_ok=True)
T=400;end=30*T;area=256*128
with (D/'timing.csv').open('w') as f:
 f.write('step_T,dt_s,velocity_si_per_lattice,area_cells,sample_stride,mode\n400,0.0128205128,78,32768,200,longspin\n')
with (D/'ledger.csv').open('w') as f:
 f.write('step,mass_lattice,px_lattice,ground_drag_lattice,ground_drag_integral_lattice,rho_mean_lattice\n')
 for s in range(0,end+1,100):f.write(f'{s},2097152,{120000+s*.01},0.0001,{s*.0001},1\n')
with (D/'profiles.csv').open('w') as f:
 f.write('step,k,u_x_mean_si\n')
 for s in range(200,end+1,200):
  for k in range(1,65):f.write(f'{s},{k},{1+.02*k}\n')
rng=np.random.default_rng(18)
with (D/'planes.bin').open('wb') as f:
 for s in range(200,end+1,200):
  a=rng.normal(0,.1,size=(2,128,256,3)).astype('<f4');a[...,0]+=1.2;a.tofile(f)
 for w in range(1,16):(D/f'window_{w}.ready').write_text(str(w*800)+'\n')
(D/'producer.done').write_text(str(end)+'\n')
print('STUB_ONLY 30T 15 WINDOWS',flush=True)
