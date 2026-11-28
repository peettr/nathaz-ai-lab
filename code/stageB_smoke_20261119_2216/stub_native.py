#!/usr/bin/env python3
"""Local worker handoff and statistics fixture. NEVER physical evidence."""
import math,os,pathlib,struct,time
p=pathlib.Path(os.environ['T17_B_DIR']);p.mkdir(exist_ok=True)
with (p/'timing.csv').open('w') as f:
 f.write('attempt,equilibrium_end_step,passed,half_T_steps,dt_s,velocity_si_per_lattice,area_cells,sample_stride,mode\n')
 f.write('0,2000,pending,200,0.01282051,78,32768,50,smoke\n')
with (p/'ledger.csv').open('w') as f:
 f.write('step,mass_lattice,px_lattice,ground_drag_lattice,ground_drag_integral_lattice,rho_mean_lattice\n')
 for step in range(0,2801,50): f.write(f'{step},2097152,100,.42,{step*.42},1\n')
(p/'v0_0.ready').write_text('2000\n')
for _ in range(200):
 if (p/'v0_0.decision').exists():break
 time.sleep(.02)
assert (p/'v0_0.decision').read_text().strip()=='pass'
(p/'statistics_start.txt').write_text('2000\n')
with (p/'profiles.csv').open('w') as f:
 f.write('step,k,u_x_mean_si\n')
 for step in range(2050,2801,50):
  for k in range(1,65):
   u=.27810/.4*math.log(((k-.5)+.024)/.024)
   f.write(f'{step},{k},{u:.12g}\n')
with (p/'planes.bin').open('wb') as f:
 for frame in range(16):
  for k in (3,10):
   u=.27810/.4*math.log(((k-.5)+.024)/.024)
   for y in range(128):
    for x in range(256):
     fluct=.3*math.sin(2*math.pi*x/256+frame*.1)+.2*math.sin(2*math.pi*y/128+frame*.05)
     f.write(struct.pack('<fff',u+fluct,.4*fluct,.2*fluct))
(p/'producer.done').write_text('2800\n')
print('SYNTHETIC_FIXTURE_ONLY',flush=True)
