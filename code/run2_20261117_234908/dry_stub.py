#!/usr/bin/python3.10
"""Fixture-only executable writing a small-height synthetic VTK; no simulation."""
import os,sys
from pathlib import Path
import numpy as np
conf=Path(sys.argv[1]);assert conf.is_file() and conf.parent.resolve()==Path.cwd()
assert (Path.cwd()/'proj_temp/CaseE_PF.stl').is_file()
label=Path.cwd().name.removeprefix('case_');assert label in ('E_s101_off','E_s102_off')
assert f'vk_inlet_seed = {label.split("_")[1][1:]}' in conf.read_text()
cl=Path(os.environ['LUW_CAPTURE_CL']);assert cl.name==label+'_actual_opencl.cl';cl.write_text('// fixture-only, actual solver invocation replaced\n')
d=Path.cwd()/'RESULTS/vtk';d.mkdir(parents=True);n=500*500*82
with (d/'CaseE_avg-fixture.vtk').open('xb') as f:
 f.write(f'# vtk DataFile Version 3.0\nSYNTHETIC FIXTURE\nBINARY\nDATASET STRUCTURED_POINTS\nDIMENSIONS 500 500 82\nORIGIN 0 0 -20\nSPACING 1 1 1\nPOINT_DATA {n}\n'.encode())
 for key,c in [('u_avg',3),('rho_avg',1),('fluid',1),('tke',1),('speed_mean',1),('speed2_mean',1)]:
  f.write(f'SCALARS {key} float {c}\nLOOKUP_TABLE default\n'.encode())
  # Chunked writes keep host memory bounded. All fixture sites are fluid.
  a=np.full(250000*c, 1 if key in ('fluid','speed_mean','u_avg') else .5,dtype='>f4')
  if key=='speed_mean':a+=.1*(label=='E_s102_off')
  for k in range(82):f.write(a.tobytes())
print('STUB_INVOKED',label,flush=True)
