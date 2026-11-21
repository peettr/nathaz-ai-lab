#!/usr/bin/env python3
"""Read all serial nut values after forced final write; fail closed."""
import argparse,json,math,re
from pathlib import Path
from post_gate import scalars
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
assert not a.out.exists()
try:
    log=(a.root/'log.pimpleFoam').read_text(errors='replace')
    assert re.search(r'(?m)^End\s*$',log),'missing End'
    times=[float(x) for x in re.findall(r'(?m)^Time =\s*([0-9.eE+-]+)\s*$',log)]
    assert times and times[-1]>=.002-1e-8,times[-1] if times else 'no Time'
    names=[d for d in (a.root/'case').iterdir() if d.is_dir() and re.fullmatch(r'\d+(?:\.\d+)?',d.name) and float(d.name)>.0019]
    assert len(names)==1,[str(n) for n in names]
    f=names[0]/'nut'
    internal=scalars(f,'internalField');building=scalars(f,'boundaryField.building.value')
    assert all(math.isfinite(x) and x>=0 for x in internal+building),'nonfinite/negative nut'
    assert all(x==0 for x in building),'building nut nonzero'
    assert len(internal)>100000 and len(building)>1,'insufficient field values'
    result={'pass':True,'final_time':times[-1],'file':str(f),'internal_count':len(internal),'internal_min':min(internal),'internal_max':max(internal),'building_count':len(building),'building_max_abs':max(map(abs,building))}
except Exception as e:result={'pass':False,'error':str(e)}
a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print(result)
if not result['pass']:raise SystemExit(1)
