#!/usr/bin/env python3
"""Patch a freshly copied scratch case; never operate on an old run root."""
from pathlib import Path
import sys,re,math
c=Path(sys.argv[1]); ztop=64; kappa=.41; z0=.03; ustar=kappa*10/math.log((8+z0)/z0)
zero=c/'0'
assert (zero/'k').is_file() and (zero/'omega').is_file() and not (zero/'nuTilda').exists()
# New SA transport variable: high-Re log-layer approximation, dimension m2/s.
s=(zero/'k').read_text().replace('object k;', 'object nuTilda;').replace('[0 2 -2 0 0 0 0]', '[0 2 -1 0 0 0 0]')
s=s.replace('internalField uniform 0.5;', 'internalField uniform 0.1;')
s=re.sub(r'top\s*\{[^}]*\}',f'top {{type fixedValue; value uniform {kappa*ustar*(ztop+z0):.12g};}}',s)
s=re.sub(r'type kqRWallFunction; value uniform 0.5;', 'type fixedValue; value uniform 0;',s)
# Temporary inlet value is overwritten face-by-face after the final snappy mesh.
s=re.sub(r'inlet\s*\{[^}]*\}', 'inlet { type fixedValue; value uniform 0.1; }',s)
(zero/'nuTilda').write_text(s)
(zero/'k').unlink();(zero/'omega').unlink()
t=(c/'constant/turbulenceProperties').read_text(); assert 'RASModel kOmegaSST' in t
(c/'constant/turbulenceProperties').write_text(t.replace('RASModel kOmegaSST','RASModel SpalartAllmaras'))
f=c/'system/fvSchemes';t=f.read_text();assert 'div(phi,k)' in t and 'div(phi,omega)' in t
t=t.replace('div(phi,k) bounded Gauss upwind;', 'div(phi,nuTilda) bounded Gauss upwind;').replace('div(phi,omega) bounded Gauss upwind;','')
f.write_text(t)
# Keep B2 nonorthogonal correction, roof layers, relaxation, 5000 steps.
assert not (zero/'k').exists() and not (zero/'omega').exists()
assert 'nuTilda' in f.read_text() and 'SpalartAllmaras' in (c/'constant/turbulenceProperties').read_text()
print('SA_PATCH_OK',c)
