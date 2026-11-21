"""Read-only Case E geometry proxy audit for two-point hat kernel; no solver."""
import json
import sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
P0 = HERE.parent / 'phase0_geometry'
sys.path.insert(0, str(P0))
from ibm_geometry import read_case_e, clean_mesh, voxel_proxy


def run():
    tri, _ = clean_mesh(read_case_e())
    solid, odd = voxel_proxy(tri)
    assert odd == 0
    # Reuse the precise Phase-0 markers; never regenerate or change their geometry.
    with np.load(P0 / 'v2/CaseE_markers_h1p0.npz') as f:
        points = f['X']
    nz, ny, nx = solid.shape
    # Two-sided solid proxy at 1 or 2 integer spacings, separately.
    near = {}
    for width in (1, 2):
        mask = np.zeros_like(solid)
        for axis in (1, 2):
            plus = np.zeros_like(solid); minus = np.zeros_like(solid)
            for d in range(1, width+1):
                sl = [slice(None)] * 3; dst = [slice(None)] * 3
                sl[axis] = slice(d, None); dst[axis] = slice(None, -d)
                minus[tuple(sl)] |= solid[tuple(dst)]
                plus[tuple(dst)] |= solid[tuple(sl)]
            mask |= plus & minus & ~solid
        near[width] = mask
    shell = np.zeros_like(solid)
    total = {'solid_support': 0, 'incomplete': 0, 'ground_z_le_0': 0,
             'narrow_1': 0, 'narrow_2': 0, 'any_narrow_1_cell': int(near[1].sum()),
             'any_narrow_2_cell': int(near[2].sum())}
    # Hat phi(r)=max(1-|r|,0), two per axis, 8 nodes for noninteger markers.
    # Integer-aligned markers have a zero-weight neighbor; no closed support assumed.
    for lo in range(0, len(points), 30000):
        p = points[lo:lo+30000].astype(np.float64)
        lower = np.floor(p).astype(np.int32)
        any_solid = np.zeros(len(p), bool)
        invalid = np.zeros(len(p), bool)
        ground = np.zeros(len(p), bool)
        narrow1 = np.zeros(len(p), bool)
        narrow2 = np.zeros(len(p), bool)
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    x = lower[:,0]+dx; y=lower[:,1]+dy; z=lower[:,2]+dz
                    weight = np.maximum(1-np.abs(p[:,0]-x),0)*np.maximum(1-np.abs(p[:,1]-y),0)*np.maximum(1-np.abs(p[:,2]-z),0)
                    active = weight > 1e-14
                    inside = (x>=0)&(x<nx)&(y>=0)&(y<ny)&(z>=0)&(z<nz)
                    invalid |= active & ~inside
                    ground |= active & (z<=0)
                    ids = np.flatnonzero(active & inside)
                    occ = solid[z[ids],y[ids],x[ids]]
                    any_solid[ids] |= occ
                    narrow1[ids] |= near[1][z[ids],y[ids],x[ids]]
                    narrow2[ids] |= near[2][z[ids],y[ids],x[ids]]
                    chosen=ids[occ]
                    shell[z[chosen],y[chosen],x[chosen]]=True
        for key, array in [('solid_support',any_solid),('incomplete',invalid),('ground_z_le_0',ground),('narrow_1',narrow1),('narrow_2',narrow2)]:
            total[key] += int(array.sum())
    total.update({'markers':int(len(points)), 'solid_voxels':int(solid.sum()),
                  'solid_to_fluid_unique':int(shell.sum()), 'kernel':'hat: max(1-abs(r),0); 8 possible nodes',
                  'proxy':'Phase-0 half-open z-section parity; not GPU flags',
                  'narrow_definition':'fluid cell with solids on both +/- x or +/- y within 1 or 2 grid steps; does not identify distinct buildings'})
    out=HERE/'two_point_proxy.json'
    out.write_text(json.dumps(total,indent=2))
    print(json.dumps(total,indent=2))

if __name__ == '__main__':
    run()
