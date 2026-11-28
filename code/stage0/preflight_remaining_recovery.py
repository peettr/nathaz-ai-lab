#!/usr/bin/env python3
"""Read-only preflight of staged recovery roots on CRC."""
import json, hashlib, subprocess
from pathlib import Path
base=Path('/groups/kareem/[用户]/L22_6')
submission=Path('./22_Lab/06_Logs/l22_6/v3/stage0/submission.jsonl')
# The submission manifest is on 工作站, not CRC: enumerate staged REC roots instead.
expected='331bf927ebd9933eabb56e07c2f0911f040437cd5ffb4f2227ba2de3653bf394'
rows=[]
for root in sorted(base.glob('L22_6_v3S0_REC_*_20261127')):
    script=root/'run.sh'; analyzer=root/'analyze_v3_numpy1.py'
    if not script.is_file() or not analyzer.is_file(): continue
    if (root/'scheduler.log').exists() or (root/'run.exitcode').exists():
        rows.append({'tag':root.name.removeprefix('L22_6_v3S0_REC_').removesuffix('_20261127'),'status':'already_started'});continue
    text=script.read_text(); tag=root.name.removeprefix('L22_6_v3S0_REC_').removesuffix('_20261127')
    assert 'cd '+str(root)+' || exit 99' in text
    assert 'm_mem_free=4G' in text and 'h_rt=01:00:00' in text
    assert hashlib.sha256(analyzer.read_bytes()).hexdigest()==expected
    source=base/f'L22_6_v3S0_{tag}_20261127'
    assert (source/'run.exitcode').read_text().strip()=='1'
    assert 'End' in (source/'pimpleFoam.log').read_text()[-2000:]
    assert (source/'case/postProcessing/InletPatch/0/U').is_file()
    a=subprocess.run(['bash','-n',str(script)],capture_output=True,text=True)
    assert a.returncode==0,(root,a.stderr)
    b=subprocess.run(['qsub','-w','v',str(script)],cwd=str(root),capture_output=True,text=True)
    assert b.returncode==0,(root,b.stdout,b.stderr)
    rows.append({'tag':tag,'status':'preflight_pass'})
print(json.dumps(rows))
