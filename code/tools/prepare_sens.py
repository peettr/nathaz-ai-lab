#!/usr/bin/env python3
"""Stage immutable R1 candidate snapshots, submit scripts and preflight ledger."""
from pathlib import Path
import os
import hashlib, json, tarfile, csv
S=Path('./22_Lab/06_Logs/l22_6/sessions')
OUT=S/'crc_C1'
import sys
K='S'; OUT=S/sys.argv[1]; IDS=sys.argv[2:]  # 反馈轮：python3 prepare_rk.py <k> <输出目录名> <id...>（只 T03、只 claude）
rows=[]
for ident in IDS:
    model,ident=ident.split('_',1); task='T03'
    source=S/'sens'/f'{model}_{ident}'
    assert source.is_dir(); assert not (S/'sens'/f'{model}_{ident}_grade.json').exists()
    root=f'/groups/kareem/[用户]/L22_6/L22_6_SENS_{model}_{ident}_20261105'+os.environ.get('ROOTSUF','')
    stem=f'{model}_{ident}'
    tar=OUT/(stem+'.tar.gz')
    entries={}
    with tarfile.open(tar,'w:gz') as tf:
     for f in sorted(source.rglob('*')):
      if f.is_file():
       rel=f.relative_to(source)
       entries[str(rel)]=hashlib.sha256(f.read_bytes()).hexdigest()
       tf.add(f,arcname='candidate/'+str(rel))
    script=OUT/(stem+'.sh')
    block=('module load openfoam/10.0/gcc/11.5.0 || exit 21\n'
           'export MPI_ROOT=/software/m/mpich/4.3.2/gcc/11.5.0\n'
           'export MPI_ARCH_FLAGS=-DMPICH_SKIP_MPICXX\n'
           'export MPI_ARCH_INC="-isystem $MPI_ROOT/include"\n'
           'export MPI_ARCH_LIBS="-L$MPI_ROOT/lib -lmpi"\n'
           'source /software/o/openfoam/10.0-mpich/OpenFOAM-10/etc/bashrc\n'
           'src_rc=$?; [ "$src_rc" -eq 0 ] || exit 22\n'
           'command -v blockMesh >/dev/null || exit 23\n'
           'python3 /groups/kareem/[用户]/L22_6/L22_6_T03_grade_v2_code/grade_T03.py "$ROOT/candidate" '
           '--work-root "${ROOT}/solver_work" '
           '--baseline-json /groups/kareem/[用户]/L22_6/L22_6_T03_v12_analysis_20261021_02/metrics_v12.json '
           '--template-case /groups/kareem/[用户]/L22_6/L22_6_T03_v12_grade_launcher_20261021_01/clean_B1 '
           '--out "$ROOT/grade.json" > "$ROOT/grade.log" 2>&1\n')
    text=(f'#!/bin/bash\n#$ -N R{K}c{ident.replace("_","")[:7]}\n#$ -S /bin/bash\n#$ -q hpc\n'
          f'#$ -l h_rt=06:00:00\n#$ -l m_mem_free=2G\n#$ -l h=!(d24cepyc154|d24cepyc161|d24cepyc162)\n#$ -j y\n#$ -o scheduler.log\n#$ -r n\n'
          f'ROOT={root}\ncd "$ROOT" || exit 99\n'
          'finish() { rc=$?; printf "%s\\n" "$rc" > "$ROOT/run.exitcode"; exit "$rc"; }\ntrap finish EXIT\n'
          f'sleep {len(rows)*13}\n'
          'export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1\n'+block)
    script.write_text(text)
    rows.append(dict(model=model,id=ident,task=task,root=root,archive=str(tar),run_script=str(script),input_sha256=entries,
                     tar_sha256=hashlib.sha256(tar.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(script.read_bytes()).hexdigest()))
(OUT/'manifest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
print('candidates=',len(rows))
