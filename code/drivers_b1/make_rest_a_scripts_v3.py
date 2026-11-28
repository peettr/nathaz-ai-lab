#!/usr/bin/env python3
"""Prepare immutable, independent UGE A job scripts; does not submit."""
import hashlib
from pathlib import Path
p = Path(__file__).resolve().parent
root = '/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x/inputs_N1N3N4_v1'
for event in ('N1','N3','N4'):
    for lead in ('24h','48h','72h'):
        if (event,lead)==('N3','24h'):
            continue
        work=f'{root}/ops_{event}_{lead}_A_v3'
        name=f'gc37x_{event}_{lead}_A3'
        script=f'''#!/bin/bash
#$ -N {name}
#$ -q long
#$ -pe smp 1
#$ -l h_rt=12:00:00
#$ -l m_mem_free=16G
#$ -hard
#$ -l hostname=!d24cepyc154*&!d24cepyc161*&!d24cepyc162*
#$ -o {work}/qsub.out
#$ -e {work}/qsub.err
ROOT={root}
WORK={work}
cd "$WORK" || exit 90
module load python/3.12.15 || exit 91
PY=$ROOT/.venv/bin/python
"$PY" -c 'import numpy,pygrib,xarray,netCDF4; print("IMPORT_OK")' || exit 92
export GC37_EVENT={event}
"$PY" -u "$ROOT/run_crc_inputs_b3.py" --event {event} --lead {lead} > "$WORK/worker.log" 2>&1
rc=$?
printf '%s\\n' "$rc" > "$WORK/exitcode"
exit "$rc"
'''
        target=p/f'submit_{event}_{lead}_A_v3.sh'
        if target.exists():
            raise FileExistsError(target)
        target.write_text(script)
        print(target,hashlib.sha256(script.encode()).hexdigest())
