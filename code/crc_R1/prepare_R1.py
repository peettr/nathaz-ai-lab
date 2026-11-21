#!/usr/bin/env python3
"""Stage immutable R1 candidate snapshots, submit scripts and preflight ledger."""
from pathlib import Path
import hashlib, json, tarfile, csv
S=Path('./22_Lab/06_Logs/l22_6/sessions')
OUT=S/'crc_R1'
rows=[]
for model in ('gpt','gemini'):
 for task in ('T01','T03'):
  for condition in ('W','N'):
   for repeat in (1,2,3):
    ident=f'{task}_{condition}_r{repeat}'
    source=S/model/ident/'cand_R1'
    assert source.is_dir()
    assert not (S/model/ident/'grade_R1.json').exists(), (model,ident)
    root=f'/groups/kareem/[用户]/L22_6/L22_6_R1_{model}_{ident}_20261023'
    stem=f'{model}_{ident}'
    tar=OUT/(stem+'.tar.gz')
    entries={}
    with tarfile.open(tar,'w:gz') as tf:
     for f in sorted(source.rglob('*')):
      if f.is_file():
       rel=f.relative_to(source)
       entries[str(rel)]=hashlib.sha256(f.read_bytes()).hexdigest()
       tf.add(f,arcname='candidate/'+str(rel))
    assert entries
    script=OUT/(stem+'.sh')
    duration='00:30:00' if task=='T01' else '06:00:00'
    block=(f'module load python/3.12.15 || exit 21\n'
           f'python3 /groups/kareem/[用户]/L22_6/L22_6_T01_grade_v2_code/score_T01.py "$ROOT/candidate" '
           f'--truth /groups/kareem/[用户]/L22_6/L22_6_T01_grade_v2_code/truth_C2.json '
           f'--q-csv /groups/kareem/[用户]/L22_6/L22_6_T01_grade_v2_code/Q_curves.csv '
           f'--out "$ROOT/grade.json" > "$ROOT/grade.log" 2>&1\n') if task=='T01' else (
           'module load openfoam/10.0/gcc/11.5.0 || exit 21\n'
           'export MPI_ROOT=/software/m/mpich/4.3.2/gcc/11.5.0\n'
           'export MPI_ARCH_FLAGS=-DMPICH_SKIP_MPICXX\n'
           'export MPI_ARCH_INC="-isystem $MPI_ROOT/include"\n'
           'export MPI_ARCH_LIBS="-L$MPI_ROOT/lib -lmpi"\n'
           'source /software/o/openfoam/10.0-mpich/OpenFOAM-10/etc/bashrc\n'
           'src_rc=$?; [ "$src_rc" -eq 0 ] || exit 22\n'
           'command -v blockMesh >/dev/null || exit 23\n'
           'python3 /groups/kareem/[用户]/L22_6/L22_6_T03_grade_v2_code/grade_T03.py "$ROOT/candidate" '
           f'--work-root "${{ROOT}}/solver_work" '
           '--baseline-json /groups/kareem/[用户]/L22_6/L22_6_T03_v12_analysis_20261021_02/metrics_v12.json '
           '--template-case /groups/kareem/[用户]/L22_6/L22_6_T03_v12_grade_launcher_20261021_01/clean_B1 '
           '--out "$ROOT/grade.json" > "$ROOT/grade.log" 2>&1\n')
    text=(f'#!/bin/bash\n#$ -N R1{model[0]}{ident.replace("_","")[:7]}\n#$ -S /bin/bash\n#$ -q hpc\n'
          f'#$ -l h_rt={duration}\n#$ -l m_mem_free=2G\n#$ -j y\n#$ -o scheduler.log\n#$ -r n\n'
          f'ROOT={root}\ncd "$ROOT" || exit 99\n'
          'finish() { rc=$?; printf "%s\\n" "$rc" > "$ROOT/run.exitcode"; exit "$rc"; }\ntrap finish EXIT\n'
          'export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1\n'
          +block)
    script.write_text(text)
    rows.append(dict(model=model,id=ident,task=task,root=root,archive=str(tar),run_script=str(script),input_sha256=entries,
                     tar_sha256=hashlib.sha256(tar.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(script.read_bytes()).hexdigest()))
assert len(rows)==24
(OUT/'manifest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
with (OUT/'jobs.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['model','id','task','root','job','registration','status']);w.writeheader()
 for r in rows:w.writerow({k:r.get(k,'') for k in w.fieldnames})
print('candidates=',len(rows),'total archive bytes=',sum(Path(r['archive']).stat().st_size for r in rows))
