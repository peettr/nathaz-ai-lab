#!/usr/bin/env python3
"""Only the NACA0012 wing nut patch is changed, in the scratch copy."""
import re,sys
from pathlib import Path
p=Path(sys.argv[1]); t=p.read_text()
pattern=r'(\"\(wing\.\*\)\"\s*\{\s*type\s+)nutUSpaldingWallFunction(\s*;\s*value\s+)[^;]+;'
u,n=re.subn(pattern,r'\1fixedValue\2uniform 0;',t)
assert n==1, n
p.write_text(u)
print('LOWRE_WING_NUT=fixedValue uniform 0')
