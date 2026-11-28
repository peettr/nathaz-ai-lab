"""Generate fresh BG remote workers and controllers from audited Case D retry9."""
from pathlib import Path
import json,shutil,re,hashlib,time
BASE=Path(__file__).resolve().parent;SRC=BASE/'CaseD_retry9_20261115_0756'
for case in ('BG_1H','BG_3H'):
 tag=case.lower().replace('_','');ts=time.strftime('%Y%m%d_%H%M')
 D=BASE/f'{case}_run_{ts}';assert not D.exists();D.mkdir()
 stage=BASE/case/'bg_stage.tar.gz';assert stage.is_file()
 shutil.copyfile(stage,D/'bg_stage.tar.gz')
 for name in ('verify_source.py','gpu_probe.py','launch.py','check.py','controller.py'):
  s=(SRC/name).read_text().replace('luw-c38-cased-r9-20261115',f'luw-c38-{tag}-{ts}').replace('Case D',case).replace('caseD',case).replace('CASE_D', 'BG')
  if name=='controller.py':
   s=s.replace(f'remote_{case}.py','remote_BG.py').replace(f'{case}_result.zip','bg_result.zip')
   s=s.replace("(D/'source_parts').glob('part_*')", "(D.parent/'CaseD_retry9_20261115_0756'/'source_parts').glob('part_*')")
   s=s.replace("NAME='luw-c38-cased-r9-20261115'",f"NAME='luw-c38-{tag}-{ts}'")
   s=s.replace('4.96/rate','1.96/rate')
   s=s.replace("'cased_stage.tar.gz'","'bg_stage.tar.gz'").replace("'/content/cased_stage.tar.gz'","'/content/bg_stage.tar.gz'")
   s=s.replace("(D/'diagnostic_extract.py','/content/diagnostic_extract.py')", "(D/'diagnostic_extract.py','/content/diagnostic_extract.py')")
   s=s.replace("'pointvalues.json','geometry_gate.json','solver_exit.json','sha256.json','profiles_upstream.json','profiles_open_streets.json','vtk_header_sha256.json','planes_1_2_3_5_10m.npz'","'pointvalues.json','geometry_gate.json','solver_exit.json','sha256.json','profiles_upstream.json','profiles_open_streets.json','vtk_header_sha256.json'")
   s=s.replace('len(pts[\'rows\'])==99',f"len(pts['rows'])=={195 if case=='BG_1H' else 200}")
   s=s.replace('npoints=99',f"npoints={195 if case=='BG_1H' else 200}")
   s=s.replace('5 CU predicted exceedance','2 CU predicted exceedance')
   s=s.replace('gpu_selected=None','gpu_selected=None')
   # BG stage and remote worker use names BG_1H/3H, not lower-case caseD spellings.
   s=s.replace("(D/'remote_BG.py'", "(D/'remote_BG.py'")
   s=s.replace("(D/'bg_stage.tar.gz'", "(D/'bg_stage.tar.gz'")
   s=s.replace("'result.zip',str(D/'caseD_result.zip')","'result.zip',str(D/'bg_result.zip')")
   s=s.replace("D/'caseD_result.zip'","D/'bg_result.zip'")
   # Parent file has literal caseD_result lower-case; replace after other edits.
   s=s.replace('caseD_result.zip','bg_result.zip')
   s=s.replace("'--expect-hours','1.5','--max-hours','2'","'--expect-hours','0.5','--max-hours','1'")
   s=s.replace("'--no-remind','--detach'","'--no-remind','--detach'")
  if name=='launch.py':s=s.replace('remote_caseD.py','remote_BG.py').replace('remote_BG.py','remote_BG.py')
  if name=='check.py':s=s.replace('remote_caseD.py','remote_BG.py')
  (D/name).write_text(s)
 # simple wrapper metadata; remote worker assembled separately, not a launched job.
 (D/'RUN_META.json').write_text(json.dumps({'case':case,'steps':14487 if case=='BG_1H' else 43461,'mean_window':9960 if case=='BG_1H' else 29880,'stride':18 if case=='BG_1H' else 54,'domain':(340,220,120) if case=='BG_1H' else (1020,660,360),'remote':f'/content/luw-c38-{tag}-{ts}'},indent=2))
 print(D)
