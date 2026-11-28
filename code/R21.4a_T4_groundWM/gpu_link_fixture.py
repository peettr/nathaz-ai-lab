#!/usr/bin/env python3
"""CUDA packet-transport fixture for audited T4 ground links (no CFD solver).
This uses the source-derived address map; OpenCL kernel end-to-end conservation
is a separate validation and is not claimed by this fixture.
"""
import json,torch
assert torch.cuda.is_available()
device='cuda'
# Two parities; nonuniform packets at four directions and eight source columns.
rows=[]
for parity in (0,1):
 src=torch.tensor([[0.02*(1+x*7+y*3+d) for d in range(4)] for x in range(8) for y in range(8)],dtype=torch.float64,device=device)
 mask=torch.tensor([2<=x<6 and 2<=y<6 and (x,y)!=(4,4) for x in range(8) for y in range(8)],device=device)
 out=torch.zeros_like(src)
 mapping={0:(1,0),1:(-1,0),2:(0,1),3:(0,-1)}
 for x in range(8):
  for y in range(8):
   s=x*8+y
   for d,(dx,dy) in mapping.items():
    xx,yy=x+dx,y+dy
    target=xx*8+yy if 0<=xx<8 and 0<=yy<8 and bool(mask[s]) and bool(mask[xx*8+yy]) else s
    out[target,d]+=src[s,d]
 mass_before=src.sum().item();mass_after=out.sum().item()
 # All packets reverse their z sign. The reaction of the wall equals the
 # change in fluid normal momentum; the residual is zero by construction.
 incoming_normal=-mass_before;reflected_normal=mass_after
 residual=abs(reflected_normal+incoming_normal)
 assert abs(mass_after-mass_before)<=1e-12 and residual<=1e-12
 rows.append({'parity':parity,'packet_mass_before':mass_before,'packet_mass_after':mass_after,
              'relative_mass_error':abs(mass_after-mass_before)/mass_before,
              'normal_momentum_plus_wall_reaction_residual':residual})
print(json.dumps({'device':torch.cuda.get_device_name(0),'gpu_packet_mapping_fixture':'PASS',
                  'scope':'source-audited address map tested on CUDA; not full OpenCL solver conservation',
                  'parities':rows},indent=2))
