#!/usr/bin/env python3
from pathlib import Path
import hashlib
here=Path(__file__).resolve().parent
out=here/'a_resume_launchers_v3';out.mkdir(exist_ok=True)
root='/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x/inputs_N8N9N10_v1'
py='/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x/inputs_N1N3N4_v1/.venv/bin/python'
for e in ('N8','N9','N10'):
 work=f'{root}/ops_{e}_72h_A_v3'
 name=f'gcx2_{e}_72_A3'
 text=f'''#!/bin/bash
#$ -N {name}
#$ -q long
#$ -pe smp 1
#$ -l h_rt=12:00:00
#$ -l m_mem_free=16G
#$ -hard
#$ -l hostname=!d24cepyc154*&!d24cepyc161*&!d24cepyc162*
#$ -o {work}/qsub.out
#$ -e {work}/qsub.err
cd {work} || exit 90
module load python/3.12.15 || exit 91
{py} -c 'import numpy,pygrib,xarray,netCDF4; print("IMPORT_OK")' || exit 92
export GC37_EVENT={e}
{py} -u {root}/run_crc_inputs_b2_v3.py --event {e} --lead 72h > {work}/worker.log 2>&1
rc=$?
printf '%s\\n' "$rc" > {work}/exitcode
exit "$rc"
'''
 dest=out/f'submit_{e}_72h_A_v3.sh'
 if dest.exists():assert dest.read_text()==text
 else:dest.write_text(text)
 print(dest,hashlib.sha256(dest.read_bytes()).hexdigest())
