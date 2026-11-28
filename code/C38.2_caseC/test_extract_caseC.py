#!/usr/bin/env python3
"""Tiny synthetic VTK parser and S1 trilinear/scalar-mean test; no CFD result."""
from pathlib import Path
import struct
import tempfile
from extract_caseC import Field, sample

with tempfile.TemporaryDirectory(prefix='extract_fixture_',dir=Path(__file__).parent) as root:
    p=Path(root)/'synthetic.vtk'
    dims=(4,4,4);n=64
    with p.open('wb') as f:
        f.write(b'# vtk DataFile Version 3.0\nfixture\nBINARY\nDATASET STRUCTURED_POINTS\nDIMENSIONS 4 4 4\nORIGIN 250 150 -2\nSPACING 2 2 2\nPOINT_DATA 64\nSCALARS u_avg float 3\nLOOKUP_TABLE default\n')
        for _ in range(n): f.write(struct.pack('>fff',1.,0.,0.))
        for name,v in [('speed_scalar_avg',2.),('rho_avg',1.),('fluid',1.),('tke',0.)]:
            f.write(f'SCALARS {name} float 1\nLOOKUP_TABLE default\n'.encode())
            for k in range(n): f.write(struct.pack('>f',0. if name=='fluid' and k<16 else v))
    field=Field(p)
    try:
        q={'point_id':'fixture','x':'0','y':'0','z':'2'}
        result=sample(field,q,wall=-1.,offset=(0.,0.))
        assert result['sample_z_m']==1. and result['actual_agl_m']==2.
        assert result['u_mean_mps']==1. and result['scalar_speed_mean_mps']==2.
        assert result['solid_weight']==0 and not result['clamped']
        print('SYNTHETIC_PARSER_AND_SCALAR_MEAN_PASS',result['u_mean_mps'],result['scalar_speed_mean_mps'])
    finally:field.close()
