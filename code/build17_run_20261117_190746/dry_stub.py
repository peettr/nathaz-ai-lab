#!/usr/bin/python3.10
"""Local-only fake solver: deterministic 500x500x4 legacy binary VTK."""
import os,sys
from pathlib import Path
import numpy as np
conf=Path(sys.argv[1]); assert conf.resolve().parent==Path.cwd() and conf.is_file()
assert (Path.cwd()/'proj_temp/CaseE_PF.stl').is_file() and (Path.cwd()/'wind_bc/profile.dat').is_file()
label=conf.parent.name
seed=102 if label=='E_s102_on' else 101
assert f'vk_inlet_seed = {seed}' in conf.read_text()
assert (Path(sys.argv[0]).resolve().parents[1].name=='city_off')==label.endswith('_off')
cl=Path(os.environ['LUW_CAPTURE_CL']); assert cl.name==f'{label}_actual_opencl.cl'
cl.write_text('// FIXTURE ONLY, not compiled OpenCL: '+label+'\n')
dest=Path.cwd()/'RESULTS/vtk';dest.mkdir(parents=True)
n=500*500*4
with (dest/'CaseE_avg-fixture.vtk').open('xb') as f:
    f.write(f'# vtk DataFile Version 3.0\nSYNTHETIC FIXTURE\nBINARY\nDATASET STRUCTURED_POINTS\nDIMENSIONS 500 500 4\nORIGIN 0 0 0\nSPACING 1 1 1\nPOINT_DATA {n}\n'.encode())
    for key,c in [('u_avg',3),('rho_avg',1),('fluid',1),('tke',1),('speed_mean',1),('speed2_mean',1)]:
        f.write(f'SCALARS {key} float {c}\nLOOKUP_TABLE default\n'.encode()); a=np.zeros(n*c,dtype='>f4')
        if key=='fluid':a[3:]=1
        if key=='speed_mean':a[:]=1+('on' in label)+(seed==102)
        f.write(a.tobytes())
print('T9B_OUTER_FLAGS total=54 TYPE_S=20 TYPE_E=34 bad=0')
print('T9B_MISSING_PATCH path=.luwpf/apply_profile_boundaries patch_sampler=not_used missing_patch_samples=0')
print('STUB_INVOKED' ,label,'samples at 2.5 m; fake VTK only',flush=True)
