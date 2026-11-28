#!/usr/bin/env python3
"""Read-only segment validation; all provenance stored outside old D1 tree."""
import json, re, sys
from pathlib import Path
root=Path(sys.argv[1]); segment=sys.argv[2]; old=Path(sys.argv[3])
logpath=old/'log.restart' if segment=='restart' else root/'log.later'
log=logpath.read_text()
times=re.findall(r'^Time = ([0-9]+(?:\.[0-9]+)?)s?\s*$',log,re.M)
assert len(times)==5,(segment,times)
assert re.search(r'^End\s*$',log,re.M)
base=old/'segments/restart/Solving' if segment=='restart' else root/'segments/later/Solving'
dirs=sorted(base.glob('PresCorr-*'))
assert len(dirs)==20,(segment,len(dirs))
entries=[]
for d in dirs:
    m=json.loads((d/'meta.json').read_text())
    assert any(abs(float(m['time'])-float(t))<1e-7 for t in times),(d,m['time'],times)
    assert all((d/f).is_file() for f in ('A.mtx.gz','b.npy','x_initial.npy','x_openfoam.npy','meta.json')),d
    entries.append({'system':d.name,'time':m['time'],'segment':segment,'source_checkpoint':'44',
                    'inlet_seed':'TInF wall-clock seed, value unavailable','source_root':str(old if segment=='restart' else root)})
out=root/f'provenance_{segment}.json'
assert not out.exists(),out
out.write_text(json.dumps({'segment':segment,'times':times,'entries':entries},indent=2)+'\n')
print(segment,len(times),len(entries),flush=True)
