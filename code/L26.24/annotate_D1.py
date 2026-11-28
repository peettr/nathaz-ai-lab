#!/usr/bin/env python3
"""Validate segment step counts and enrich fresh D1 metadata with provenance."""
import json,re,sys
from pathlib import Path
root=Path(sys.argv[1]); segment,logname=sys.argv[2:4]; enabled=int(sys.argv[4]); expected={'restart':5,'middle':20,'later':5}[segment]
log=(root/logname).read_text()
times=re.findall(r'^Time = (\S+)',log,re.M)
assert len(times)==expected,(segment,len(times),times)
assert re.search(r'^End\s*$',log,re.M),(segment,'missing End')
if enabled:
    dirs=sorted((root/'segments'/segment/'Solving').glob('PresCorr-*'))
    assert len(dirs)==20,(segment,len(dirs))
    for d in dirs:
        mpath=d/'meta.json'; meta=json.loads(mpath.read_text())
        assert meta['time'] in times,(d,meta['time'],times)
        assert 'segment' not in meta
        meta.update(segment=segment,source_checkpoint='44',source_case='R25.2 S2 checkpoint',
                    inlet_seed='TInF wall-clock seed; exact value unavailable',
                    original_config_manifest='s2_sha256_compare.json')
        mpath.write_text(json.dumps(meta,indent=2)+'\n')
(root/f'timing.{segment}.json').write_text(json.dumps({'segment':segment,'steps':times,'exported_systems':20 if enabled else 0},indent=2)+'\n')
print(segment,'steps',len(times),'systems',20 if enabled else 0,flush=True)
