#!/usr/bin/env python3
"""Synthetic fixture executable; only tests paths, extraction and transport."""
import os,pathlib,struct,sys
cfg=pathlib.Path(sys.argv[1]);base=cfg.parent;o=base/'RESULTS';o.mkdir(exist_ok=True)
if os.environ.get('LUW_COMPILE_ONLY'):
 print('FIXTURE_COMPILE_ONLY '+base.name,flush=True);sys.exit(0)
label=base.name.removeprefix('case_');content=base.parent.parent
cl=pathlib.Path(os.environ['LUW_CAPTURE_CL']);cl.write_text('FIXTURE_NOT_OPENCL\n')
if label=='E3_native':
 (content/'t15_e3_force_tau.csv').write_text('step,x,y,tau_f_x_lattice,applied_force_x_lattice,area_lattice,relative_error\n1,2,2,0.125,-0.125,1,0\n')
else:
 v=o/'vtk';v.mkdir();p=v/'fixture_avg-000000100.vtk';nx,ny,nz=8,6,55;n=nx*ny*nz
 with p.open('wb') as f:
  f.write(('# vtk DataFile Version 3.0\nfixture NOT PHYSICS\nBINARY\nDATASET STRUCTURED_POINTS\nDIMENSIONS 8 6 55\nORIGIN 0 0 -20\nSPACING 1 1 1\nPOINT_DATA '+str(n)+'\nSCALARS u_avg float 3\nLOOKUP_TABLE default\n').encode())
  f.write(struct.pack('>'+str(n*3)+'f',*([0.1,0.,0.]*n)))
  for name,value in (('rho_avg',1.),('fluid',1.),('tke',0.01),('speed_mean',0.1),('speed2_mean',0.01)):
   f.write(('SCALARS '+name+' float 1\nLOOKUP_TABLE default\n').encode())
   f.write(struct.pack('>'+str(n)+'f',*([value]*n)))
 (o/'wall_tau_actual.csv').write_text('x,y,count,tau_abs_over_rho_lattice,fx_over_rho_lattice,fy_over_rho_lattice,ustar_mps\n2,2,100,0.1,-0.1,0,0.3\n')
 (o/'t3d_geometry_gate.csv').write_text('x_m,y_m,first_fluid_k,first_fluid_z_m,expected_z_m,pass\n2,2,21,1,1,1\n')
print('FIXTURE_ONLY',label,flush=True)
