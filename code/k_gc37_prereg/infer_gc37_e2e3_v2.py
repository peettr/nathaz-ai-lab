#!/usr/bin/env python3
"""Six frozen E2/E3 cycles; refuse to infer until complete numeric gate passed."""
import datetime as dt,hashlib,json,pathlib,subprocess,sys
R=pathlib.Path('/content/r234c_gc37_E2E3');R.mkdir(exist_ok=True)
BBOX=pathlib.Path('/content/domain_bbox_gc37.json')
EVENTS=json.loads(pathlib.Path('/content/event_times_gc37.json').read_text())
LOG=R/'infer_e2e3.log'
def emit(*v):
 with LOG.open('a') as f:print(dt.datetime.now().astimezone().isoformat(),*v,file=f,flush=True)
def stage(label,cmd):
 emit('STAGE_START',label)
 with (R/(label+'.log')).open('x') as f:p=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT)
 emit('STAGE_END',label,p.returncode)
 if p.returncode:raise RuntimeError((label,p.returncode))
try:
 summary=json.loads((R/'INPUT_NUMERIC_GATE_E2E3_V2_SUMMARY.json').read_text())
 assert (R/'INPUT_NUMERIC_GATE_E2E3_V2.passed').read_text().strip()=='PASS'
 assert summary['all_pass'] and summary['expected_files']==summary['examined_files'],summary
 stage('weights',['python3','/content/stage_gc37_weights_e2e3.py'])
 for event in ('E2','E3'):
  for lead in ('24h','48h','72h'):
   t0=dt.datetime.fromisoformat(EVENTS[event]['leads'][lead]['t0']); end=dt.datetime.fromisoformat(EVENTS[event]['end'])
   steps=int((end-t0).total_seconds()/21600);cycle=t0.strftime('%Y%m%d%H')
   stage('prepare_'+cycle,['python3','/content/prepare_gc37_gfs_2024_e2e3_v2.py','--cycle',cycle,'--root',str(R)])
   stage('infer_'+cycle,['python3','/content/run_gc37_raw_e2e3.py','--cycle',cycle,'--event',event,'--steps',str(steps),'--root',str(R),'--bbox',str(BBOX)])
   folder=R/f'forecast_{cycle}_{steps}step'; files=sorted(folder.glob('step_*.npz'))
   assert len(files)==steps,(cycle,len(files),steps)
   manifest=[{'path':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest()} for p in files]
   (R/f'RAW_MANIFEST_{cycle}.json').write_text(json.dumps(manifest,indent=2))
   emit('RAW_READY',event,cycle,len(files),sum(x['bytes'] for x in manifest))
 (R/'infer_e2e3.done').write_text('SUCCESS\n');emit('SUCCESS_ALL')
except Exception as exc:
 emit('FAILED',repr(exc));(R/'infer_e2e3.failed').write_text(repr(exc)+'\n');raise
