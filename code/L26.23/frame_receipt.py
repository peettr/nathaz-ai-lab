#!/usr/bin/env python3
"""Independently count the frozen S2 time window, no source mutations."""
import json,sys
from pathlib import Path
building,ref,params,out=map(Path,sys.argv[1:])
assert not out.exists()
cfg=json.loads(params.read_text());lo=cfg['peak_start_s'];hi=cfg['peak_end_s']
def count(p):
    nwin=npeak=0
    with p.open() as f:
        for line in f:
            if not line or line.lstrip().startswith('#'):continue
            t=float(line.split(maxsplit=1)[0]);nwin+=10-1e-9<=t<=44+1e-9;npeak+=lo+1e-9<t<=hi+1e-9
    return nwin,npeak
b=count(building);r=count(ref)
receipt={'building_full_frames':b[0],'building_peak_frames':b[1],'ref_full_frames':r[0],'ref_peak_frames':r[1],'expected_full':34001,'expected_peak':32952,'pass':b==(34001,32952) and r==(34001,32952)}
out.write_text(json.dumps(receipt,indent=2)+'\n');print(receipt)
if not receipt['pass']:raise SystemExit(1)
