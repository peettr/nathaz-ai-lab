#!/usr/bin/env python3
"""Predeclared Case A dx10 geometry gate on native voxel flags (TYPE_S=1)."""
import hashlib,json,math,re,sys
from pathlib import Path
root=Path(sys.argv[1]); log=(root/'gate.log').read_text(errors='replace')
match=re.search(r'GEOM_GATE_NATIVE_FLAGS dims=(\d+),(\d+),(\d+) bytes=(\d+)',log)
assert match,'gate did not export native flags'
nx,ny,nz,count=map(int,match.groups()); raw=(root/'caseA_dx10/native_flags_voxel.u8').read_bytes()
assert len(raw)==count==nx*ny*nz
spacing=704/70; origin=-30.0
assert (nx,ny)==(109,70) and nz>=39,(nx,ny,nz)
def flag(x,y,k):return raw[x+nx*(y+ny*k)]
def solid(x,y,k):return bool(flag(x,y,k)&1)
open_xy=[(10,10),(20,20),(60,50)]
# k=0 boundary, k=1,2 lie below STL's physical z=0; k=3 is first expected fluid.
open_rows=[{'xy':[x,y],'solid_k0_to_k4':[solid(x,y,k) for k in range(5)],'flags_k0_to_k4':[flag(x,y,k) for k in range(5)]} for x,y in open_xy]
center=(35,35)
center_rows=[k for k in range(nz) if solid(*center,k)]
roof=max(k for k in center_rows if k>3) if any(k>3 for k in center_rows) else -1
roof_effective_m=origin+roof*spacing-spacing/2 if roof>=0 else None
# 4m original geometry: STL min=-20, top=64, lattice top 1+(84/4)=22;
# strict upper endpoint leaves last solid k=21; effective z= -20+21*4-2=62m.
reference_4m_effective_roof_m=62.0
solid_interior=sum(bool(v&1) for v in raw)
checks={
 'all_open_subground_solid':all(all(row['solid_k0_to_k4'][:3]) for row in open_rows),
 'first_fluid_at_stl_ground_layer':all(row['solid_k0_to_k4'][:3]==[True]*3 and not row['solid_k0_to_k4'][3] for row in open_rows),
 'building_bottom_not_suspended':all(solid(*center,k) for k in range(1,4)),
 'roof_within_one_grid':roof>=0 and abs(roof_effective_m-reference_4m_effective_roof_m)<=spacing,
 'global_solid_far_above_63':solid_interior>630,
}
result={'native_flags_sha256':hashlib.sha256(raw).hexdigest(),'dimensions':[nx,ny,nz], 'spacing_m':spacing,'origin_z_m':origin,'open_ground':open_rows,'building_center_xy_index':center,'building_solid_layers':center_rows,'roof_effective_m':roof_effective_m,'reference_4m_effective_roof_m':reference_4m_effective_roof_m,'global_solid_count_including_boundary':solid_interior,'checks':checks,'pass':all(checks.values())}
(root/'gate.json').write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result,indent=2));sys.exit(0 if result['pass'] else 2)
