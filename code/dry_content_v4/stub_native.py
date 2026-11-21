#!/usr/bin/python3
"""Synthetic solver only; not physics evidence. Exercise real worker and V0 branches."""
import os,pathlib,csv,math,time
import numpy as np
p=pathlib.Path(os.environ['T17_B_DIR']);p.mkdir(exist_ok=True)
seed=os.environ['T17_B_SEED'];group=p.name.split('_s')[0]
half=200;stride=50;initial=2000
with (p/'timing.csv').open('w') as f:
 f.write('attempt,equilibrium_end_step,passed,half_T_steps,dt_s,velocity_si_per_lattice,area_cells,sample_stride,mode\n')
 f.flush()
 def v0(a,end):
  f.write(f'{a},{end},pending,{half},0.01282051,78,32768,{stride},production\n');f.flush()
  (p/f'v0_{a}.ready').write_text(str(end)+'\n')
  for _ in range(1000):
   if (p/f'v0_{a}.decision').exists():return (p/f'v0_{a}.decision').read_text().strip()
   time.sleep(.01)
  raise RuntimeError('no V0 response')
 with (p/'ledger.csv').open('w') as l:
  l.write('step,mass_lattice,px_lattice,ground_drag_lattice,ground_drag_integral_lattice,rho_mean_lattice\n')
  for step in range(0,4001,50):
   # seed 2 initially fails V0, then a second window passes.
   px=100+(step/2000)*30 if seed=='2' and step<=2000 else (130 if seed=='2' else 100)
   l.write(f'{step},2097152,{px},0.42,{step*.42},1\n')
 (p/'ledger.csv').flush() if False else None
 first=v0(0,2000)
 if seed=='2':
  assert first=='extend',first
  second=v0(1,2400);assert second=='pass',second
  start=2400
 else:
  assert first=='pass',first
  start=2000
(p/'statistics_start.txt').write_text(str(start)+'\n')
with (p/'profiles.csv').open('w') as f:
 f.write('step,k,u_x_mean_si\n')
 for step in range(start+50,start+800+1,50):
  for k in range(1,65):
   u=.27810/.4*math.log(((k-.5)+.024)/.024)
   f.write(f'{step},{k},{u:.12g}\n')
x=np.arange(256)[None,:];y=np.arange(128)[:,None]
with (p/'planes.bin').open('wb') as f:
 for j in range(16):
  for k in (3,10):
   u=.27810/.4*math.log(((k-.5)+.024)/.024)
   fluct=.3*np.sin(2*np.pi*x/256+j*.1)+.2*np.sin(2*np.pi*y/128+j*.05)
   a=np.empty((128,256,3),dtype='<f4');a[:,:,0]=u+fluct;a[:,:,1]=.4*fluct;a[:,:,2]=.2*fluct;f.write(a.tobytes())
(p/'producer.done').write_text(str(start+800)+'\n')
print('SYNTHETIC_FIXTURE_ONLY',group,seed,first,flush=True)
