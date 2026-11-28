#!/usr/bin/env python3
"""Stage immutable R1 candidates and frozen grader, without running candidates."""
from pathlib import Path
import json, hashlib, tarfile
BASE=Path(__file__).resolve().parents[1]
PROBE=BASE/'probe'
ROOT=Path('/groups/kareem/[用户]/L22_6')
DATE='20261127'
ids=[f'{m}_{c}_b{k}' for m in ('gpt','gemini') for c in ('W','N') for k in (1,2)]
archive=PROBE/'grade_R1_stage.tar.gz'
manifest=[]
for identity in ids:
    src=PROBE/identity/'cand_R1'/'t02.py'
    assert src.is_file(),src
    run=ROOT/f'L22_6_T02_probe_{identity}_{DATE}_01'
    assert not (PROBE/identity/'grade_R1.json').exists()
    manifest.append({'id':identity,'root':str(run),'sha256':hashlib.sha256(src.read_bytes()).hexdigest()})
assert not archive.exists(),archive
with tarfile.open(archive,'x:gz') as tar:
    for row in manifest:
        identity=row['id']; rootname=Path(row['root']).name
        for source,target in ((PROBE/identity/'cand_R1'/'t02.py','candidate/t02.py'),
                              (BASE/'grader'/'grade_T02.py','grade_T02.py'),
                              (BASE/'calib_T02.csv','calib_T02.csv')):
            tar.add(source,arcname=f'{rootname}/{target}')
        sh=PROBE/identity/'run_grade_R1.sh'
        assert not sh.exists(),sh
        sh.write_text(f'''#!/bin/bash
#$ -cwd
#$ -N L22_6_T02_{identity}
#$ -q hpc
#$ -l h_rt=01:00:00
#$ -l m_mem_free=4G
#$ -l hostname='!d24cepyc154*&!d24cepyc161*&!d24cepyc162*&!d24cepyc160*'
ROOT={row['root']}
cd "$ROOT" || exit 80
module load python/3.12.15
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
python3 grade_T02.py candidate --truth calib_T02.csv --out grade.json --work "$ROOT" > grader.log 2>&1
rc=$?
printf '%s\\n' "$rc" > run.exitcode
exit "$rc"
''')
        tar.add(sh,arcname=f'{rootname}/run.sh')
card=PROBE/'EXPERIMENT_CARD_R1.md'
assert not card.exists(),card
card.write_text('''# T02 探针 R1 CRC 评分实验卡\n\n① 假设：冻结打分台能将每份原样候选输出 scored 或可反馈的 candidate_failed，不以调度退出码代替级别。\n② 改动：八份独立 R1 候选逐项评分；不修改候选、真值或打分台。\n③ 配置：grader/grade_T02.py、calib_T02.csv；sha256 见 staging_manifest_R1.json。各候选 sha256 同表。资源 CO-61e4f41c。\n④ 作业：提交后逐项填作业号、运行根、日志、rc-job 回执；提交记录见 submission_R1.jsonl。\n⑤ 判据：提交前写定 11-27 07:00 美东：八份逐项保留原始 JSON；harness_fault 不反馈；candidate_failed 按协议 §4 反馈。终态诊断待回填。\n''')
mp=PROBE/'staging_manifest_R1.json'
assert not mp.exists(),mp
mp.write_text(json.dumps({'resource':'CO-61e4f41c','grader_sha256':hashlib.sha256((BASE/'grader'/'grade_T02.py').read_bytes()).hexdigest(),'truth_sha256':hashlib.sha256((BASE/'calib_T02.csv').read_bytes()).hexdigest(),'jobs':manifest},indent=2)+'\n')
print('archive',archive,'sha256',hashlib.sha256(archive.read_bytes()).hexdigest(),'jobs',len(manifest))
