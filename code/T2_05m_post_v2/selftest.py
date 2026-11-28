#!/usr/bin/env python3
"""Tiny synthetic VTK and mask/point regression; never load production field."""
import importlib.util, pathlib, tempfile, struct, numpy as np
spec=importlib.util.spec_from_file_location('post',pathlib.Path(__file__).with_name('post_t2.py'))
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
with tempfile.TemporaryDirectory() as d:
 f=pathlib.Path(d)/'tiny.vtk';nx=ny=nz=4;N=nx*ny*nz
 with f.open('wb') as w:
  w.write(b'# vtk DataFile Version 3.0\ntiny\nBINARY\nDATASET STRUCTURED_POINTS\nDIMENSIONS 4 4 4\nORIGIN 0 0 0\nSPACING 1 1 1\nPOINT_DATA 64\nSCALARS u_avg float 3\nLOOKUP_TABLE default\n')
  for i in range(N):w.write(struct.pack('>fff',float(i%4),1.,2.))
  for name in ('rho_avg','fluid','tke','speed_mean','speed2_mean'):
   w.write(f'SCALARS {name} float 1\nLOOKUP_TABLE default\n'.encode())
   for i in range(N):w.write(struct.pack('>f',float(i%4) if name=='speed_mean' else 1.))
 v=p.vtk_open(f);assert v['dims']==(4,4,4) and float(v['fields']['speed_mean'][2,2,2])==2.
 sample=p.point_sample(v,{'xls_xy':[-249.50008,-250.60004]},(1.,1.,0.))
 assert sample['fluid_corners']==8 and sample['solid_weight']==0 and abs(sample['Su']-2)<1e-8,sample
 tri=np.array([[[1.,1.,0.],[3.,1.,0.],[3.,3.,0.]],[[1.,1.,0.],[3.,3.,0.],[1.,3.,0.]]])
 seg=[[(1.,1.),(3.,1.)],[(3.,1.),(3.,3.)],[(3.,3.),(1.,3.)],[(1.,3.),(1.,1.)]]
 m=p.mask(np.array([.5,1.5,2.5,3.5]),np.array([.5,1.5,2.5,3.5]),seg)
 assert m.tolist()==[[False]*4,[False,True,True,False],[False,True,True,False],[False]*4],m
 print('SELFTEST_PASS tiny_vtk_header_fields_point_and_mask')
