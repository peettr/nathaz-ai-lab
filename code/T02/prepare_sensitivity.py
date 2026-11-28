#!/usr/bin/env python3
"""Generate fresh immutable scheduler scripts; do not run the solver here."""
from pathlib import Path
p=Path(__file__).resolve().parent/'sensitivity_scripts'
p.mkdir(exist_ok=True)
source='/groups/kareem/[用户]/L22_6/L22_6_T02_MC_large_03_20261127'
for tag,dt,v0 in [('dt_half',.005,0),('tanh_v001',.01,.001)]:
    path=p/f'run_{tag}.sh'
    if path.exists():raise FileExistsError(path)
    root=f'/groups/kareem/[用户]/L22_6/L22_6_T02_sensitivity_{tag}_20261127_01'
    text=f'''#!/bin/bash
#$ -cwd
#$ -q hpc
#$ -l h_rt=06:00:00
#$ -l m_mem_free=4G
#$ -l hostname='!d24cepyc154*&!d24cepyc161*&!d24cepyc162*&!d24cepyc160*'
#$ -N L22_6_T02_sens_{tag}
ROOT={root}
cd "$ROOT" || exit 98
finish() {{ rc=$?; printf '%s\\n' "$rc" > "$ROOT/run.exitcode"; }}
trap finish EXIT
module load python/3.12.15 || exit 21
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
python3 mc_t02.py large --nu 0.9783145940392678 --n 200 --dt {dt} --T 1800 --burn 300 --v0 {v0} --seed 20261127 --out mc_result.json > mc.log 2>&1
'''
    path.write_text(text)
    print(path,root)
