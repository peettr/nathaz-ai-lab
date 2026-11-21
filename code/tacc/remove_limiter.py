#!/usr/bin/env python3
"""Only delete the explicitly named grad(U) limiter in a fresh scratch case."""
from pathlib import Path
import sys

p = Path(sys.argv[1])
s = p.read_text()
needle = 'grad(U) cellLimited Gauss linear 1;'
assert s.count(needle) == 1, f'expected exactly one grad(U) limiter in {p}'
assert 'default Gauss linear;' in s
new = s.replace(needle, '')
assert 'grad(U) cellLimited' not in new
p.write_text(new)
print('LIMITER_REMOVED', p, 'gradSchemes default Gauss linear')
