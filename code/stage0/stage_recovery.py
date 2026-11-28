#!/usr/bin/env python3
"""Stage postprocessing only, in fresh CRC roots. Never mutate source cases."""
import json
from pathlib import Path
import shutil

BASE=Path('/groups/kareem/[用户]/L22_6')
ANALYZER=BASE/'L22_6_v3S0_recovery_tools_20261127'/'analyze_v3_numpy1.py'
CARD=BASE/'L22_6_v3S0_DBG_01_20261127'/'EXPERIMENT_CARD.md'
assert ANALYZER.is_file() and CARD.is_file()
for source in sorted(BASE.glob('L22_6_v3S0_*_20261127')):
    name=source.name.removeprefix('L22_6_v3S0_').removesuffix('_20261127')
    if name.startswith(('DBG_', 'REC_')): continue
    e=source/'run.exitcode'
    if not e.exists(): continue
    if e.read_text().strip() != '1':
        print(json.dumps({'source':str(source),'skipped':'non-1 exit'}),flush=True);continue
    solver=source/'pimpleFoam.log'
    probes=source/'case/postProcessing/InletPatch/0/U'
    if not (solver.exists() and 'End' in solver.read_text()[-2000:] and probes.is_file() and probes.stat().st_size>100_000_000):
        print(json.dumps({'source':str(source),'skipped':'solver/probe unverified'}),flush=True);continue
    dest=BASE/f'L22_6_v3S0_REC_{name}_20261127'
    if dest.exists():
        print(json.dumps({'source':str(source),'skipped':'recovery root exists','root':str(dest)}),flush=True);continue
    dest.mkdir(mode=0o700)
    shutil.copy2(ANALYZER,dest/'analyze_v3_numpy1.py')
    shutil.copy2(CARD,dest/'EXPERIMENT_CARD.md')
    script=f'''#!/bin/bash
#$ -N S0R_{name}
#$ -S /bin/bash
#$ -q hpc
#$ -l h_rt=01:00:00
#$ -l m_mem_free=4G
#$ -l hostname='!d24cepyc154*&!d24cepyc160*&!d24cepyc161*&!d24cepyc162*'
#$ -j y
#$ -o scheduler.log
#$ -r n
ROOT={dest}
cd {dest} || exit 99
finish() {{ rc=$?; printf '%s\\n' "$rc" > "$ROOT/run.exitcode"; }}
trap finish EXIT
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
set -e
python3 "$ROOT/analyze_v3_numpy1.py" {source}/case "$ROOT/metrics.json" > "$ROOT/analyze.log" 2>&1
'''
    (dest/'run.sh').write_text(script)
    (dest/'run.sh').chmod(0o700)
    print(json.dumps({'source':str(source),'root':str(dest),'group_seq':name}),flush=True)
