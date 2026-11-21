#!/usr/bin/env python3
"""Validate every periodic ground neighbour in E3-specific source."""
import json,pathlib
R=pathlib.Path(__file__).resolve().parent
s=(R/'e3_new_kernel_container.cl').read_text()
for token in ('const uxx layer=j[6]-(uxx)xyz.x-(uxx)xyz.y*(uxx)def_Nx','const uxx gx_p=layer+','const uxx gx_m=layer+','const uxx gy_p=layer+','const uxx gy_m=layer+'):
 assert token in s,token
N=24;Ny=24;Nz=12;z=1;ground=(z-1)*N*Ny
boundary=[]
for y in range(Ny):
 for x in range(N):
  j6=ground+x+N*y;layer=j6-x-N*y
  near=(layer+(x+1)%N+N*y,layer+(x+N-1)%N+N*y,layer+x+N*((y+1)%Ny),layer+x+N*((y+Ny-1)%Ny))
  expected=(ground+(x+1)%N+N*y,ground+(x+N-1)%N+N*y,ground+x+N*((y+1)%Ny),ground+x+N*((y+Ny-1)%Ny))
  assert near==expected and all(0<=v<N*Ny for v in near)
  if x in (0,1,22,23) or y in (0,1,22,23):boundary.append((x,y))
assert len(boundary)==176
out={'checked_columns':N*Ny,'boundary_columns':len(boundary),'periodic_neighbour_indices_all_match':True,'range':[0,N*Ny-1], 'source_file':'e3_new_kernel_container.cl'}
(R/'PERIODIC_INDEX_TEST.json').write_text(json.dumps(out,indent=2)+'\n')
print(out)
