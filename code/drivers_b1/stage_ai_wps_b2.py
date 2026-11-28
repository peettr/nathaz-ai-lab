#!/usr/bin/env python3
"""Stage only new v2 AI WPS roots; never alter previous artifacts."""
from pathlib import Path
import os, hashlib, shutil
P=Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x')
INPUT=P/'inputs_N1N3N4_v1'
SRC=Path('./23_AI_Weather/06_Logs/k_gc37x_prereg/drivers_b1/build_gc37x_wps_ai_b2.py')
# This script runs on CRC: the v2 source is uploaded to the new staging root first.
SRC=P/'ai_stage_b2'/'build_gc37x_wps_ai_b2.py'
cycles={'N1':{24:'2024061418',48:'2024061318',72:'2024061218'},'N3':{24:'2022070418',48:'2022070318',72:'2022070218'},'N4':{24:'2022042200',48:'2022042100',72:'2022042000'}}
infer={('N1',24):'infer_b1_blackwell_8_v2',('N1',48):'infer_b1_blackwell_8_v2',('N1',72):'infer_b1_blackwell_recover_N1_72_v3',('N3',24):'infer_b1_blackwell_recover_N3_24_DX3_v5',('N3',48):'infer_b1_blackwell_recover_N3_48_v4',('N3',72):'infer_b1_blackwell_recover_N3_72_v3',('N4',24):'infer_b1_blackwell_recover_N4_24_v3',('N4',48):'infer_b1_blackwell_recover_N4_48_v3',('N4',72):'infer_b1_blackwell_recover_N4_72_v3'}
assert hashlib.sha256(SRC.read_bytes()).hexdigest()=='fbf61a6032a34df2ba8d9d4395204a31dacf50e6b27b605e613442c8ae6601b8'
for event,mapping in cycles.items():
 raw=P/f'gc37_raw_{event}_v1'
 if raw.exists(): raise FileExistsError(raw)
 raw.mkdir()
 for lead,cycle in mapping.items():
  source=P/infer[event,lead]/'raw'/event/cycle
  assert (source/'RAW_READY').is_file() and (source/'SHA256SUMS').is_file(),source
  assert len(list(source.glob('step_*.npz')))=={24:5,48:9,72:13}[lead],source
  (raw/cycle).symlink_to(source,target_is_directory=True)
  gfs=P/f'drivers_{event}_v1'/f'ops_{event}_{lead}h_GFS_b1'
  assert (gfs/f'SHARED_SURFACE_{cycle}.npz').is_file(),gfs
  assert (gfs/f'SHARED_SURFACE_{cycle}.json').is_file(),gfs
  assert len(list((P/f'drivers_{event}_v1'/'GFS'/cycle).glob('FILE:*')))=={24:6,48:10,72:14}[lead]
  root=P/f'drivers_{event}_v1'/f'ops_{event}_{lead}h_AI_b2'
  if root.exists(): raise FileExistsError(root)
  root.mkdir()
  for name,source_file in [('build_gc37x_wps_ai_b2.py',SRC),('COMMON_LEVELS.txt',gfs/'COMMON_LEVELS.txt'),('event_times_bbox_gc37x.json',gfs/'event_times_bbox_gc37x.json'),('wps_format5.py',gfs/'wps_format5.py')]:
   shutil.copy2(source_file,root/name)
  script=root/f'submit_{event}_{lead}h_AI_b2.sh'
  script.write_text(f'''#!/bin/bash
#$ -N gc37x_{event}_{lead}h_AI_b2
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
export GC37_LEAD={lead}
export GC37_OPS_ROOT={root}
export GC37_AI_RAW_DIR={raw}
export PYTHONPATH={root}
{INPUT}/.venv/bin/python -c 'import numpy,pygrib,scipy; import wps_format5; print("IMPORT_OK")' || exit 92
{INPUT}/.venv/bin/python -u {root}/build_gc37x_wps_ai_b2.py --cycle {cycle} --arm AI --raw-dir {INPUT}/raw/{cycle} > {root}/worker.log 2>&1
rc=$?
printf '%s\\n' "$rc" > {root}/exitcode
exit "$rc"
''')
  script.chmod(0o755)
  print(event,lead,cycle,root,source,flush=True)
