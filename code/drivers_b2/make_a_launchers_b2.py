#!/usr/bin/env python3
"""Freeze B2 per-cycle UGE A launchers; never submits a job."""
import json, pathlib, hashlib
HERE=pathlib.Path(__file__).resolve().parent
OUT=HERE/'a_launchers_v1';OUT.mkdir(exist_ok=True)
CONFIG=json.loads((HERE.parent/'event_times_bbox_gc37x.json').read_text())['events']
BASE='/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x'
ROOT=f'{BASE}/inputs_N8N9N10_v1'
PY=f'{BASE}/inputs_N1N3N4_v1/.venv/bin/python'
def emit(path,text):
 if path.exists(): assert path.read_text()==text,('existing differs',str(path))
 else:path.write_text(text)
for event in ('N8','N9','N10'):
 for lead in ('24h','48h','72h'):
  assert CONFIG[event]['leads'][lead]['t0']
  work=f'{ROOT}/ops_{event}_{lead}_A_v1'
  name=f'gcx2_{event}_{lead[0:2]}_A'
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
cd {work} || exit 90
module load python/3.12.15 || exit 91
{PY} -c 'import numpy,pygrib,xarray,netCDF4; print("IMPORT_OK")' || exit 92
export GC37_EVENT={event}
{PY} -u {ROOT}/run_crc_inputs_b1.py --event {event} --lead {lead} > {work}/worker.log 2>&1
rc=$?
printf '%s\\n' "$rc" > {work}/exitcode
exit "$rc"
'''
  emit(OUT/f'submit_{event}_{lead}_A_v1.sh',script)
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.glob('*.sh')}
emit(OUT/'SHA256.json',json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'launchers':len(manifest),'root':str(OUT)},indent=2))
