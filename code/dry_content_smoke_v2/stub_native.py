#!/usr/bin/env python3
"""Local real-worker handoff fixture only. NOT a physical solver."""
import csv, os, pathlib, struct, time
p=pathlib.Path(os.environ['T17_B_DIR']);p.mkdir(exist_ok=True)
with (p/'timing.csv').open('w') as f:
 f.write('attempt,equilibrium_end_step,passed,half_T_steps,dt_s,velocity_si_per_lattice,area_cells,mode\n')
 f.write('0,1000,pending,8975,0.01282051,78,32768,smoke\n')
(p/'v0_0.ready').write_text('1000\n')
for _ in range(100):
 if (p/'v0_0.decision').exists():break
 time.sleep(.02)
assert (p/'v0_0.decision').read_text().strip()=='pass'
(p/'statistics_start.txt').write_text('1000\n')
with (p/'ledger.csv').open('w') as f:
 f.write('step,mass_fluid_lattice,px_fluid_lattice,ground_drag_lattice,ground_drag_integral_lattice,rho_mean_lattice\n0,2097152,100,1,0,1\n1000,2097152,100,1,1000,1\n2000,2097152,100,1,2000,1\n')
with (p/'profiles.csv').open('w') as f:
 f.write('step,k,u_x_mean_si\n')
 for k in range(1,65):f.write(f'1200,{k},{k*.01}\n')
with (p/'planes.bin').open('wb') as f:
 block=struct.pack('<fff',1.,0.,0.)*256*128
 f.write(block*2)
(p/'producer.done').write_text('2000\n')
print('FIXTURE_NATIVE_PRODUCER_ONLY',flush=True)
