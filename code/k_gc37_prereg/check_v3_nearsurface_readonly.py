#!/usr/bin/env python3
"""Read-only, data-byte comparison of v3 near-surface slabs at t0 and +6 h."""
from pathlib import Path
import struct, hashlib, json, datetime as dt
R=Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37/drivers_gc37_v3')
def slabs(path):
    b=path.read_bytes();p=0;d={}
    while p<len(b):
        rec=[]
        for _ in range(5):
            n=struct.unpack_from('>I',b,p)[0];rec.append(b[p+4:p+4+n]);p+=8+n
        h=rec[1];field=h[60:69].decode('ascii').strip();level=int(round(struct.unpack_from('>f',h,140)[0]))
        if (field,level) in {(x,200100) for x in ('TT','UU','VV')} | {('PMSL',201300)}:
            d[field]=hashlib.sha256(rec[4]).hexdigest()
    assert len(d)==4,(path,d)
    return d
rows={}
for cycle in ('2020060806','2020060706','2020060606'):
    start=dt.datetime.strptime(cycle,'%Y%m%d%H')
    rows[cycle]={}
    for lead in (0,6):
        name=f'FILE:{(start+dt.timedelta(hours=lead)):%Y-%m-%d_%H}'
        ai=slabs(R/'AI'/cycle/name);gfs=slabs(R/'GFS'/cycle/name)
        rows[cycle][str(lead)]={k:ai[k]==gfs[k] for k in ai}
        assert all(rows[cycle][str(lead)].values()) if lead==0 else not all(rows[cycle][str(lead)].values())
print(json.dumps(rows,indent=2))
