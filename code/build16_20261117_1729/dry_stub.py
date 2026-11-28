#!/usr/bin/python3
import csv,os,pathlib,sys
p=pathlib.Path(os.environ['T9B_GATE_OUTPUT'])
channel=os.getenv('T9B_GATE_SHAPE')=='channel'
assert len(sys.argv)==1 and (not channel or os.environ['T9B_WALL_Y']=='1')
state=pathlib.Path.cwd().name.split('_')[-1]
assert p.name==('channel_y_' if channel else 'cube_')+state+'_trace.csv'
print('STUB_INVOKED',p,flush=True)
keys='step M_all fluid_rho fluid_rho_two_step wall_link_normal_flux_abs wall_tangential_speed_mean tangent_momentum'.split()
with p.open('x') as f:
 w=csv.writer(f);w.writerow(keys)
 for t in range(1001 if channel else 301):
  momentum=1-t*0.0002 if state=='off' else 1+t*0.00000001
  w.writerow((t,1,1,1,0,0,momentum))
