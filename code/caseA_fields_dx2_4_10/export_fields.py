"""TACC CPU job: read completed LUW legacy binary VTK; write per-field npy.gz."""
import gzip, hashlib, json, os, re, sys
from pathlib import Path
import numpy as np

ROOT = Path(sys.argv[1]).resolve()
SOURCES = [Path(x).resolve() for x in sys.argv[2:]]
assert len(SOURCES) == 3 and ROOT.is_dir()

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for part in iter(lambda:f.read(4*1024*1024), b''):
            h.update(part)
    return h.hexdigest()

def header(p):
    with p.open('rb') as f:
        lines=[]
        for _ in range(40):
            line=f.readline().decode('ascii','strict').strip()
            lines.append(line)
            if line == 'LOOKUP_TABLE default':
                break
        else:
            raise ValueError('VTK header missing lookup table')
        start=f.tell()
    def tuple_of(key, cast):
        return tuple(map(cast,next(s for s in lines if s.startswith(key+' ')).split()[1:]))
    dims=tuple_of('DIMENSIONS',int)
    origin=tuple_of('ORIGIN',float)
    spacing=tuple_of('SPACING',float)
    assert all(x>0 for x in dims)
    assert next(s for s in lines if s.startswith('SCALARS '))=='SCALARS u_avg float 3'
    assert 'BINARY' in lines and 'DATASET STRUCTURED_POINTS' in lines
    assert tuple_of('POINT_DATA',int)==(int(np.prod(dims)),)
    return dims,origin,spacing,start

def field_offsets(p,n,start):
    result={'u_avg':start}; pos=start+n*3*4
    with p.open('rb') as f:
        for name in ('rho_avg','fluid','tke'):
            f.seek(pos)
            token=[已隐去]'ascii','strict').strip()
            lookup=f.readline().decode('ascii','strict').strip()
            assert token=[已隐去]'SCALARS {name} float 1' and lookup=='LOOKUP_TABLE default', (name,token,lookup)
            pos=f.tell();result[name]=pos;pos+=n*4
    assert pos==p.stat().st_size,(pos,p.stat().st_size)
    return result

def export(p,label,steps,window,stride):
    assert p.is_file() and p.stat().st_size>0
    dims,origin,spacing,start=header(p)
    n=int(np.prod(dims)); offsets=field_offsets(p,n,start)
    expected={'dx2':2.,'dx4':4.,'dx10':10.057143}[label]
    assert abs(spacing[0]-expected)<.1 and max(spacing)-min(spacing)<.001,(label,spacing)
    info={'source_vtk':str(p),'source_bytes':p.stat().st_size,'source_sha256':sha(p),
          'dims_xyz':dims,'origin_xyz_m':origin,'spacing_xyz_m':spacing,
          'array_shape_zyx':(dims[2],dims[1],dims[0]),'file_dtype':'<f4',
          'stats':{'run_nstep':steps,'purge_avg_steps':window,'stride_steps':stride,'sample_count':window//stride,
                   'physical_average_duration_s': None,
                   'duration_note':'Exact physical dt not independently verified; log prints rounded steps/s (dx2=34, dx4=17, dx10=7), so do not infer exact duration from those integers.'},
          'geometry':{'coordinates':'x downstream, y lateral, z above ground; wind direction 270 degrees',
                      'building_center_xy_m':[352,352], 'ground_z_m':0,
                      'offset_note':'dx2 r9 point-table (+2,+2,+2)m; dx4/dx10 one-cell horizontal shift by IoU, z shift must be judged from roof mask, never selected by MAE. Fields here are native grid, no geometry displacement applied.'},
          'quantities':{}}
    shape=(dims[2],dims[1],dims[0])
    u=np.memmap(p,dtype='>f4',mode='r',offset=offsets['u_avg'],shape=shape+(3,))
    scalar={key:np.memmap(p,dtype='>f4',mode='r',offset=offsets[key],shape=shape) for key in ('fluid','tke')}
    for key,src,units,definition in (
      ('u',u[...,0],'m/s','time-mean x velocity'),('v',u[...,1],'m/s','time-mean y velocity'),
      ('w',u[...,2],'m/s','time-mean z velocity'),('k',scalar['tke'],'m2/s2','resolved turbulent kinetic energy'),
      ('fluid',scalar['fluid'],'1','VTK fluid scalar, NOT native flags; solid mask is fluid<0.5')):
        dest=ROOT/f'{label}_{key}.npy.gz'
        assert not dest.exists(),dest
        with dest.open('xb') as raw, gzip.GzipFile(fileobj=raw,mode='wb',compresslevel=3,mtime=0) as gz:
            # numpy header + rows via bounded planes; stream little-endian float32
            from numpy.lib import format as fmt
            fmt.write_array_header_2_0(gz,{'descr':'<f4','fortran_order':False,'shape':shape})
            for z in range(shape[0]):
                plane=np.asarray(src[z],dtype='<f4',order='C')
                assert np.isfinite(plane).all(),(label,key,z)
                gz.write(plane.tobytes(order='C'))
        size=dest.stat().st_size
        assert size<200_000_000,(dest,size)
        info['quantities'][key]={'path':str(dest),'bytes':size,'sha256':sha(dest),'unit':units,'definition':definition}
        print(label,key,size,flush=True)
    return info

cases=[('dx2',32000,22000,40),('dx4',16000,11000,20),('dx10',6400,4400,8)]
meta={}
for (label,steps,window,stride),p in zip(cases,SOURCES):
    meta[label]=export(p,label,steps,window,stride)
assert sum(v['bytes'] for m in meta.values() for v in m['quantities'].values())<1_000_000_000,'over 1 GB: keep remote only'
with (ROOT/'meta.json').open('x') as f:
    json.dump(meta,f,indent=2)
print('TOTAL',sum(v['bytes'] for m in meta.values() for v in m['quantities'].values()),flush=True)
