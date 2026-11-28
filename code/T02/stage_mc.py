#!/usr/bin/env python3
"""CRC-only staging of eight fresh MC roots; no local solver run or qsub."""
import json,shutil
from pathlib import Path
BASE=Path('/groups/kareem/[用户]/L22_6')
SOURCE=BASE/'L22_6_T02_SL_20261127_01'
NU0='0.9783145940392678'
PLAN=[('small',NU0),('medium',NU0),('large',NU0),('X',NU0),('large','0.94'),('large','1.02'),('large','1.08'),('large','1.14')]
OUT=SOURCE/'mc_prepared.jsonl'
if OUT.exists():raise FileExistsError(OUT)
with OUT.open('x') as f:
    for index,(case,nu) in enumerate(PLAN,1):
        root=BASE/f'L22_6_T02_MC_{case}_{index:02d}_20261127'
        if root.exists():raise FileExistsError(root)
        root.mkdir(mode=0o700)
        for name in ('mc_t02.py','sl_calibration.py','tmdi_powerlaw_sl.py','filter_params.json','EXPERIMENT_CARD.md'):
            shutil.copy2(SOURCE/name,root/name)
        text=f'''#!/bin/bash
#$ -cwd
#$ -q hpc
#$ -l h_rt=06:00:00
#$ -l m_mem_free=4G
#$ -l hostname='!d24cepyc154*&!d24cepyc161*&!d24cepyc162*&!d24cepyc160*'
#$ -N L22_6_T02_{index:02d}
ROOT={root}
cd "$ROOT" || exit 98
finish() {{ rc=$?; printf '%s\\n' "$rc" > "$ROOT/run.exitcode"; }}
trap finish EXIT
module load python/3.12.15 || exit 21
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
python3 mc_t02.py {case} --nu {nu} --n 200 --dt 0.01 --T 1800 --burn 300 --seed 20261127 --out mc_result.json > mc.log 2>&1
'''
        (root/'run.sh').write_text(text)
        row={'index':index,'case':case,'nu':float(nu),'root':str(root),'n':200,'T_s':1800,'burn_s':300,'dt_s':.01,'seed':20261127}
        f.write(json.dumps(row)+'\n');f.flush();print(row,flush=True)
