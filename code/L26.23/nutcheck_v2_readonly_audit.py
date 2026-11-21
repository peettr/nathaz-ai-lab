#!/usr/bin/env python3
"""Read-only independent field audit after nutcheck_v2 wrapper gate failed."""
import json, math, re, sys
from pathlib import Path
root = Path('/groups/kareem/[用户]/L26_23_NEARWALL_R1/nutcheck_v2')
sys.path.insert(0, str(root))
from post_gate import scalars
log = (root/'log.pimpleFoam').read_text(errors='replace')
times = [float(x) for x in re.findall(r'(?m)^Time =\s*([0-9.eE+-]+)\s*s?\s*$', log)]
f = root/'case/0.002/nut'
a = scalars(f, 'internalField')
b = scalars(f, 'boundaryField/building/value')
print(json.dumps({'source': str(f), 'end': bool(re.search(r'(?m)^End\s*$', log)),
                  'last_time': times[-1] if times else None,
                  'internal_count': len(a), 'internal_min': min(a), 'internal_max': max(a),
                  'internal_finite_nonnegative': all(math.isfinite(x) and x >= 0 for x in a),
                  'building_count': len(b), 'building_min': min(b), 'building_max': max(b),
                  'building_all_zero': all(x == 0 for x in b),
                  'building_finite': all(math.isfinite(x) for x in b)}, allow_nan=False))
