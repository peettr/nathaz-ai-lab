#!/usr/bin/env python3
"""Write per-face Richards–Hoxey neutral ABL fixedValue inlet (no solver)."""
import math
import re
import struct
import sys
from pathlib import Path

case = Path(sys.argv[1])
mesh = case / 'constant/polyMesh'
boundary = (mesh / 'boundary').read_text()
m = re.search(r'\binlet\s*\{([^}]*)\}', boundary)
assert m, 'inlet patch missing'
count = int(re.search(r'nFaces\s+(\d+)', m[1])[1])
start = int(re.search(r'startFace\s+(\d+)', m[1])[1])

def binary_list(path, item_fmt, count_expected=None):
    b = path.read_bytes()
    m = re.search(rb'\n(\d+)\n\(', b)
    assert m, f'binary list not found: {path}'
    n = int(m[1]); assert count_expected is None or n == count_expected
    offset = m.end()
    size = struct.calcsize(item_fmt)
    assert b[offset + n * size:offset + n * size + 1] == b')', f'format mismatch {path}'
    return b, n, offset

pbytes, np, poff = binary_list(mesh / 'points', '<ddd')
fbytes, nf, foff = binary_list(mesh / 'faces', '<I', 465189)
assert nf >= start + count
# OpenFOAM faceCompactList: first offset array, then vertex-label array.
end_off = foff + nf * 4
assert fbytes[end_off:end_off+1] == b')', 'compact offsets not terminated'
tail = fbytes[end_off+1:]
second = re.match(rb'\s*(\d+)\s*\(', tail)
assert second, 'compact vertex list missing'
labels_n = int(second[1]); loff = end_off + 1 + second.end()
assert fbytes[loff + labels_n*4:loff + labels_n*4+1] == b')'

def offset(i): return struct.unpack_from('<I', fbytes, foff + 4*i)[0]

kappa = 0.41
z0 = 0.03
uref = 10.0
zref = 8.0
cmu = 0.09
ustar = kappa * uref / math.log((zref+z0)/z0)
values = {'U': [], 'k': [], 'omega': []}
heights = []
for face in range(start, start+count):
    a, b = offset(face), offset(face+1)
    assert 3 <= b-a <= 20 and b <= labels_n, (face,a,b)
    z = 0.0
    for j in range(a,b):
        pid = struct.unpack_from('<I', fbytes, loff+4*j)[0]
        assert pid < np
        z += struct.unpack_from('<d', pbytes, poff+24*pid+16)[0]
    z /= b-a
    assert math.isfinite(z) and z >= 0, (face,z)
    heights.append(z)
    values['U'].append(f'({ustar/kappa*math.log((z+z0)/z0):.12g} 0 0)')
    values['k'].append(f'{ustar**2/math.sqrt(cmu):.12g}')
    values['omega'].append(f'{ustar/(kappa*math.sqrt(cmu)*(z+z0)):.12g}')

for field, data in values.items():
    path = case / '0' / field
    text = path.read_text()
    pattern = r'\binlet\s*\{[^{}]*\}'
    replacement = 'inlet { type fixedValue; value nonuniform List<' + ('vector' if field == 'U' else 'scalar') + f'> {count}\n(\n' + '\n'.join(data) + '\n); }'
    text, changed = re.subn(pattern, replacement, text, count=1)
    assert changed == 1, field
    path.write_text(text)
print(f'INLET_FACES={count} Z_MIN={min(heights):.8g} Z_MAX={max(heights):.8g} USTAR={ustar:.8g} UREF8={uref} Z0={z0}')
