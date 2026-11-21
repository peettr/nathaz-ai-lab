#!/usr/bin/env python3
"""Read OpenFOAM probes from actual empty-flow run, fail closed."""
import json, math, re, sys
from pathlib import Path
case=Path(sys.argv[1]);out=Path(sys.argv[2]);root=case/'postProcessing/atBuilding'
def last(name):
 files=sorted(root.glob(f'*/{name}'))
 assert files,(name,root)
 lines=[x for f in files for x in f.read_text(errors='replace').splitlines() if x.strip() and not x.startswith('#')]
 assert lines,(name,'no data rows')
 return lines[-1]
u=last('U');k=last('k')
vec=re.findall(r'\(\s*([-+\de.E]+)\s+([-+\de.E]+)\s+([-+\de.E]+)\s*\)',u)
ks=[float(x) for x in k.split()[1:]]
assert len(vec)==len(ks)==4,(u,k)
ustar=.41*10/math.log((8+.03)/.03); k_in=ustar**2/math.sqrt(.09)
rows=[]
for z,v,kv in zip((2,4,8,16),vec,ks):
 mag=math.sqrt(sum(float(x)**2 for x in v)); expected=ustar/.41*math.log((z+.03)/.03)
 rows.append({'z':z,'U_empty':mag,'k_empty':kv,'U_inlet':expected,'k_inlet':k_in,'U_relative_deviation':(mag-expected)/expected,'k_relative_deviation':(kv-k_in)/k_in})
assert 0<rows[2]['U_empty']<30 and all(math.isfinite(r['k_empty']) for r in rows)
result={'source':'CRC G1 no-building simpleFoam empty-field probes at x=0,y=0','rows':rows,'U_at_H':rows[2]['U_empty']}
out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
