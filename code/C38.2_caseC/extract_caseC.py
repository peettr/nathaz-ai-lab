#!/usr/bin/env python3
"""Extract 120 Case C S1 values from a native round-9 mean VTK (on Colab).

No solver is run here. Refuses fields without the instantaneous scalar-speed mean.
"""
import csv
import hashlib
import json
import math
import mmap
from pathlib import Path
import struct


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


class Field:
    def __init__(self, path):
        self.path = Path(path)
        self.f = self.path.open('rb')
        self.m = mmap.mmap(self.f.fileno(), 0, access=mmap.ACCESS_READ)
        header = []
        while True:
            line = self.f.readline().decode('ascii').strip()
            header.append(line)
            if line.startswith('LOOKUP_TABLE'):
                break
            assert len(header) < 32, header
        self.header = header
        self.dims = [int(v) for v in next(x for x in header if x.startswith('DIMENSIONS')).split()[1:]]
        self.origin = [float(v) for v in next(x for x in header if x.startswith('ORIGIN')).split()[1:]]
        self.spacing = [float(v) for v in next(x for x in header if x.startswith('SPACING')).split()[1:]]
        assert header[-2] == 'SCALARS u_avg float 3', header
        assert self.spacing == [2., 2., 2.], self.spacing
        self.n = math.prod(self.dims)
        start = self.f.tell()
        self.fields = {'u_avg': (start, 3)}
        pos = start + 12*self.n
        for name in ('speed_scalar_avg', 'rho_avg', 'fluid', 'tke'):
            marker = f'SCALARS {name} float 1\nLOOKUP_TABLE default\n'.encode()
            assert self.m[pos:pos+len(marker)] == marker, (name, pos, self.m[pos:pos+90])
            pos += len(marker)
            self.fields[name] = (pos, 1)
            pos += 4*self.n
        assert pos == len(self.m), (pos, len(self.m))

    def close(self):
        self.m.close()
        self.f.close()

    def value(self, name, i, j, k):
        assert all(0 <= v < d for v, d in zip((i, j, k), self.dims))
        offset, width = self.fields[name]
        idx = i + self.dims[0]*(j + self.dims[1]*k)
        result = struct.unpack_from('>' + 'f'*width, self.m, offset + 4*width*idx)
        return result if width == 3 else result[0]

    def ij(self, x, y):
        return (round((x-self.origin[0])/2), round((y-self.origin[1])/2))


def gate(field, case):
    # Open-ground sites are well away from the central footprint; no guessed wall index.
    sites = [(20, 20), (480, 20), (20, 280), (480, 280)]
    columns = []
    for x, y in sites:
        i, j = field.ij(x, y)
        solid = [k for k in range(min(20, field.dims[2])) if field.value('fluid', i, j, k) <= .5]
        kf = next(k for k in range(2, min(28, field.dims[2])) if field.value('fluid', i, j, k) > .5)
        assert solid and solid == list(range(kf)), (x, y, solid, kf)
        columns.append({'xy_m': [x, y], 'first_fluid_k': kf,
                        'wall_label_m': field.origin[2] + (kf-.5)*2})
    assert len({q['first_fluid_k'] for q in columns}) == 1, columns
    wall = columns[0]['wall_label_m']
    # Per-case native voxel evidence at central building; geometry is not inferred from STL alone.
    roof_heights = []
    for x in range(210, 292, 2):
        for y in range(110, 192, 2):
            i, j = field.ij(x, y)
            solids = [k for k in range(columns[0]['first_fluid_k'], min(field.dims[2], 45))
                      if field.value('fluid', i, j, k) <= .5]
            if solids:
                assert solids[0] == columns[0]['first_fluid_k'], (x, y, solids[:3])
                roof_heights.append(field.origin[2] + 2*(max(solids)+.5)-wall)
    assert roof_heights, 'no building solids in central region'
    assert any(abs(z-20) <= 2 for z in roof_heights), '20 m roofs missing'
    if case == '2D':
        assert any(abs(z-40) <= 2 for z in roof_heights), '40 m roof missing'
    else:
        assert not any(z > 22 for z in roof_heights), 'unexpected tall roof'
    return {'open_columns': columns, 'ground_wall_label_m': wall,
            'central_solid_columns': len(roof_heights),
            'sampled_roof_min_max_m': [min(roof_heights), max(roof_heights)]}


def sample(field, point, wall, offset=(2., 2.)):
    x, y, h = (float(point[k]) for k in ('x', 'y', 'z'))
    xyz = (x+250+offset[0], y+150+offset[1], max(wall+h, wall+1.))
    pos = [(v-a)/d for v, a, d in zip(xyz, field.origin, field.spacing)]
    ids = [math.floor(t) for t in pos]
    frac = [t-i for t, i in zip(pos, ids)]
    assert all(0 <= i < d-1 for i, d in zip(ids, field.dims)), (xyz, ids, field.dims)
    vals = [0.]*4
    corners = []
    solid_weight = 0.
    for code in range(8):
        shift = [(code>>a)&1 for a in range(3)]
        weight = math.prod(frac[a] if shift[a] else 1-frac[a] for a in range(3))
        if weight <= 1e-12:
            continue
        i, j, k = [ids[a]+shift[a] for a in range(3)]
        fluid = field.value('fluid', i, j, k) > .5
        if not fluid:
            solid_weight += weight
        uvw = field.value('u_avg', i, j, k)
        speed = field.value('speed_scalar_avg', i, j, k)
        for a, v in enumerate((*uvw, speed)):
            vals[a] += weight*v
        corners.append({'ijk': [i,j,k], 'weight': weight, 'fluid': fluid})
    assert len(corners) and all(math.isfinite(v) for v in vals), (point, vals)
    # A solid interpolation is still reported numerically but cannot be a clear-fluid prediction.
    return {'sample_x_m': xyz[0], 'sample_y_m': xyz[1], 'sample_z_m': xyz[2],
            'actual_agl_m': xyz[2]-wall, 'clamped': xyz[2]>wall+h+1e-9,
            'u_mean_mps': vals[0], 'v_mean_mps': vals[1], 'w_mean_mps': vals[2],
            'scalar_speed_mean_mps': vals[3], 'solid_weight': solid_weight,
            'mixed_solid': solid_weight>1e-12, 'corners': corners}


def register(field, stl, case):
    """IoU against native fluid mask, independent of observed wind values."""
    from v4_alignment import footprint, labels, components
    levels = [2.,10.,18.] + ([38.] if case=='2D' else [])
    aggregate = {offset:[0,0] for offset in ((0,0),(2,0),(0,2),(2,2))}
    records=[]; base_components=None
    for level in levels:
        k=round((level-field.origin[2])/2)
        assert 0<=k<field.dims[2] and abs(field.origin[2]+2*k-level)<1e-8
        expected=labels(footprint(stl,level),field.origin,field.spacing,field.dims)
        assert expected, (case,level)
        if level==2.:
            base_components=components(expected)
            assert len(base_components)==(8 if case=='0D' else 9), (case,len(base_components))
        mi=max(0,min(i for i,j in expected)-2)
        ma=min(field.dims[0]-1,max(i for i,j in expected)+3)
        mj=max(0,min(j for i,j in expected)-2)
        mb=min(field.dims[1]-1,max(j for i,j in expected)+3)
        roi={(i,j) for i in range(mi,ma+1) for j in range(mj,mb+1)
             if field.value('fluid',i,j,k)<=.5}
        for offset in aggregate:
            sx,sy=offset[0]//2,offset[1]//2
            shifted={(i+sx,j+sy) for i,j in expected if i+sx<field.dims[0] and j+sy<field.dims[1]}
            inter=len(shifted&roi);union=len(shifted|roi)
            aggregate[offset][0]+=inter;aggregate[offset][1]+=union
            records.append({'level_m':level,'offset_xy_m':list(offset),'intersection':inter,
                            'union':union,'iou':inter/union if union else None})
    scores={str(offset):v[0]/v[1] if v[1] else None for offset,v in aggregate.items()}
    best=max(scores.values());winners=[offset for offset,v in aggregate.items() if v[1] and v[0]/v[1]==best]
    assert winners==[(2,2)], ('registration not uniquely +2 m', scores, winners)
    return {'method':'STL horizontal cuts vs native fluid-mask solids; maximum aggregate IoU before reading velocity',
            'levels_m':levels,'building_components':len(base_components),'candidate_details':records,
            'aggregate_iou':scores,'selected_offset_xy_m':[2,2],'stl_sha256':sha(stl)}


def extract(case, vtk, points, stl, dest):
    assert case in ('0D','1D','2D')
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=False)
    field = Field(vtk)
    try:
        geometry = gate(field, case)
        registration = register(field, stl, case)
        with open(points, newline='', encoding='utf-8-sig') as f:
            source = list(csv.DictReader(f))
        assert len(source)==120 and len({p['point_id'] for p in source})==120
        rows=[]; detailed=[]
        for p in source:
            info=sample(field,p,geometry['ground_wall_label_m'])
            d={'point_id':p['point_id'], 'x_m':p['x'], 'y_m':p['y'], 'z_agl_m':p['z'],
               **{k:v for k,v in info.items() if k != 'corners'}}
            rows.append(d);detailed.append({'point_id':p['point_id'], **info})
        cols=list(rows[0]); out=dest/f'caseC_{case}_pointvalues.csv'
        with out.open('x', newline='') as f:
            w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(rows)
        metadata={'case':case,'vtk_sha256':sha(vtk),'points_sha256':sha(points),
                  'vtk_header':field.header,'dims':field.dims,'origin':field.origin,'spacing':field.spacing,
                  'geometry_gate':geometry,'registration':registration,'selected_offset_xy_m':[2,2],
                  'coordinate_rule':'x_LUW=x_C38+250+2; y_LUW=y_C38+150+2; z_VTK=z_wall+z_AGL (clamp to first-fluid label)',
                  'scalar_definition':'time mean of instantaneous sqrt(u*u+v*v+w*w) at the same accumulation steps as vector means',
                  'point_count':len(rows),'clamped':sum(x['clamped'] for x in rows),
                  'mixed_solid':sum(x['mixed_solid'] for x in rows),
                  'corners':detailed, 'csv_sha256':sha(out)}
        (dest/'extraction.json').write_text(json.dumps(metadata,indent=2,allow_nan=False))
        return metadata
    finally:
        field.close()


if __name__ == '__main__':
    import argparse
    a=argparse.ArgumentParser();a.add_argument('case');a.add_argument('vtk');a.add_argument('points');a.add_argument('stl');a.add_argument('dest')
    args=a.parse_args();print(json.dumps(extract(args.case,args.vtk,args.points,args.stl,args.dest),indent=2))
