"""Audit native LUW flags (not STL proxy), no solver or GPU."""
from pathlib import Path
import numpy as np, scipy.ndimage as ndi, json
r=Path(__file__).resolve().parent
f=np.load(r/'ma010_flags_z0_62.npz')['flags']; assert f.shape==(63,500,500)
solid=(f&1)!=0
out=[]; positions=[]
for z in range(21,62):
 # Include both 3D neighboring slices; z=61 has available z=62.
 block=solid[z-1:z+2]
 count=ndi.convolve(block.astype(np.uint8),np.ones((3,3,3),np.uint8),mode='constant',cval=0)[1]
 six=(~solid[z-1]).astype(np.uint8)+(~solid[z+1]).astype(np.uint8)
 six[1:,:]+=(~solid[z][:-1,:]).astype(np.uint8);six[:-1,:]+=(~solid[z][1:,:]).astype(np.uint8)
 six[:,1:]+=(~solid[z][:,:-1]).astype(np.uint8);six[:,:-1]+=(~solid[z][:,1:]).astype(np.uint8)
 valid=(~solid[z])&(count>=13)
 iso=valid&(six<=2)
 y,x=np.nonzero(iso)
 positions.extend((int(xx),int(yy),z) for yy,xx in zip(y,x))
 out.append({'z':z,'fluid_with_26solid_ge13':int(valid.sum()),'six_passable_le2':int(iso.sum()),'xy_quadrants_isolated':[[int(iso[ya:yb,xa:xb].sum()) for xa,xb in ((0,250),(250,500))] for ya,yb in ((0,250),(250,500))]})
report={'source':'ma010_flags_z0_62.npz, native voxelized flags from stage5 Ma0.10 before initialization','range':'z21..61 inclusive, neighbor z20..62','totals':{'corner':sum(x['fluid_with_26solid_ge13'] for x in out),'isolated':len(positions)},'layers':out,'isolated_position_sample':positions[:100],'boundary_caveat':'6 connectivity counts any non-solid flag, including equilibrium; outside-of-export vertical edges not queried'}
(r/'ma010_corner_stats.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
np.savez_compressed(r/'ma010_isolated_xyz.npz',xyz=np.array(positions,dtype=np.uint16).reshape(-1,3))
print(report['totals'], 'layers',out[:2],out[-2:])
