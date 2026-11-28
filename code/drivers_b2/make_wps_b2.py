#!/usr/bin/env python3
"""Freeze B2 GFS/AI WPS scripts in distinct, not-yet-submitted roots."""
from pathlib import Path
import hashlib
import json

here = Path(__file__).resolve().parent
b1 = here.parent / 'drivers_b1'
out = here / 'wps_package_v1'
out.mkdir(exist_ok=True)
base = '/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x'
source = (b1 / 'build_gc37x_wps_gfs_b1.py').read_text()
for before, after in (("('N1','N3','N4')", "('N8','N9','N10')"),
                      ('inputs_N1N3N4_v1', 'inputs_N8N9N10_v1')):
    assert before in source
    source = source.replace(before, after)
# The AI worker imports the GFS module; keep both modules from the same frozen package.
ai_source = (b1 / 'build_gc37x_wps_ai_b2.py').read_text()
assert 'inputs_N1N3N4_v1' in ai_source
ai_source = ai_source.replace('inputs_N1N3N4_v1', 'inputs_N8N9N10_v1')
for before, after in (("('N1','N3','N4')", "('N8','N9','N10')"),
                      ('build_gc37x_wps_gfs_b1', 'build_gc37x_wps_gfs_b2'),
                      ('_GFS_b1', '_GFS_b2'),
                      ("RAW.name == f'gc37_raw_{EVENT}_v1'", "RAW.name == f'infer_b2_{EVENT}_{os.environ[\"GC37_LEAD\"]}h_v1'")):
    ai_source = ai_source.replace(before, after)

def emit(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text() != text:
        path.write_text(text)

emit(out / 'build_gc37x_wps_gfs_b2.py', source)
emit(out / 'build_gc37x_wps_ai_b2.py', ai_source)
for f in ('wps_format5.py',):
    emit(out / f, (here.parent.parent / 'k_gc37_preflight' / f).read_text())
config = json.loads((here.parent / 'event_times_bbox_gc37x.json').read_text())['events']
levels_source = '1000,975,950,925,900,850,800,750,700,650,600,550,500,450,400,350,300,250,200,150,100,70,50,30,20,10,7,5,3,2,1'
for event in ('N8', 'N9', 'N10'):
    for lead in ('24h', '48h', '72h'):
        cycle = config[event]['leads'][lead]['t0'].replace('-', '').replace(':', '').replace('T', '')[:10]
        for arm in ('GFS', 'AI'):
            root = f'{base}/drivers_{event}_v1/ops_{event}_{lead}_{arm}_b2'
            path = out / f'submit_{event}_{lead}_{arm}_b2.sh'
            py = f'{base}/inputs_N1N3N4_v1/.venv/bin/python'
            module = 'build_gc37x_wps_gfs_b2.py' if arm == 'GFS' else 'build_gc37x_wps_ai_b2.py'
            args = f'--cycle {cycle} --arm {arm} --raw-dir {base}/inputs_N8N9N10_v1/raw/{cycle}'
            script = f'''#!/bin/bash
#$ -N gcx2_{event}_{lead[:2]}_{arm}
#$ -q long
#$ -pe smp 4
#$ -l h_rt=08:00:00
#$ -l m_mem_free=8G
#$ -hard
#$ -l hostname=!d24cepyc154*&!d24cepyc161*&!d24cepyc162*
#$ -o {root}/qsub.out
#$ -e {root}/qsub.err
cd {root} || exit 90
module load python/3.12.15 || exit 91
export GC37_EVENT={event}
export GC37_LEAD={lead[:2]}
export GC37_AI_RAW_DIR={base}/infer_b2_{event}_{lead}_v1
export GC37_OPS_ROOT={root}
export PYTHONPATH={root}
{py} -c 'import numpy,pygrib,scipy; import wps_format5; print("IMPORT_OK")' || exit 92
{py} -u {root}/{module} {args} > {root}/worker.log 2>&1
rc=$?
printf '%s\\n' "$rc" > {root}/exitcode
exit "$rc"
'''
            emit(path, script)
for f in out.glob('*.py'):
    compile(f.read_text(), str(f), 'exec')
manifest = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(out.iterdir()) if f.is_file() and f.name != 'SHA256.json'}
emit(out / 'SHA256.json', json.dumps(manifest, indent=2) + '\n')
print(json.dumps({'files': len(manifest), 'directory': str(out)}, indent=2))
