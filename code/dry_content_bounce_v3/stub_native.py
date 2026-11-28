#!/usr/bin/python3.10
"""Small fixture only: synthetic solver output, never scientific evidence."""
import os,pathlib,math,time
import numpy as np
p=pathlib.Path(os.environ['T17_B_DIR']);p.mkdir(exist_ok=True)
seed=os.environ['T17_B_SEED'];NX=int(os.environ['T17_TEST_NX']);NY=int(os.environ['T17_TEST_NY']);area=NX*NY
T=400;half=200;stride=50;initial=2000;end=3200
with (p/'ledger.csv').open('x') as f:
 f.write('step,mass_lattice,px_lattice,ground_drag_lattice,ground_drag_integral_lattice,rho_mean_lattice\n')
 for step in range(0,end+1,stride):
  px=(100+30*step/2000 if seed=='2' and step<=2000 else 130 if seed=='2' else 100)
  f.write(f'{step},{64*area},{px},0.42,{step*.42},1\n')
with (p/'timing.csv').open('x') as f:
 f.write('attempt,equilibrium_end_step,passed,half_T_steps,dt_s,velocity_si_per_lattice,area_cells,sample_stride,mode\n')
 for a,step in enumerate([initial]+([initial+T] if seed=='2' else [])):
  f.write(f'{a},{step},pending,{half},0.0128205,78,{area},{stride},production\n');f.flush()
  (p/f'v0_{a}.ready').write_text(str(step)+'\n')
  for _ in range(1000):
   q=p/f'v0_{a}.decision'
   if q.exists():break
   time.sleep(.01)
  else:raise RuntimeError('V0 decision timeout')
  assert q.read_text().strip()==('extend' if seed=='2' and a==0 else 'pass')
start=2400 if seed=='2' else 2000
(p/'statistics_start.txt').write_text(str(start)+'\n')
with (p/'profiles.csv').open('x') as f:
 f.write('step,k,u_x_mean_si\n')
 for step in range(stride,start+4*half+1,stride):
  for k in range(1,65):
   u=.27810/.4*math.log((k-.5+.024)/.024)
   f.write(f'{step},{k},{u:.12g}\n')
x=np.arange(NX)[None,:];y=np.arange(NY)[:,None]
with (p/'planes.bin').open('xb') as f:
 for step in range(stride,start+4*half+1,stride):
  for k in (3,10):
   u=.27810/.4*math.log((k-.5+.024)/.024)
   fluct=.3*np.sin(2*np.pi*x/NX+step*.001)+.2*np.sin(2*np.pi*y/NY+step*.0005)
   a=np.empty((NY,NX,3),dtype='<f4');a[:,:,0]=u+fluct;a[:,:,1]=.4*fluct;a[:,:,2]=.2*fluct;f.write(a.tobytes())
(p/'producer.done').write_text(str(start+4*half)+'\n')
print('SYNTHETIC_STUB_ONLY',seed,flush=True)
