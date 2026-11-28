#!/usr/bin/env python3
"""Real worker in PAYLOAD-only sandbox, only solver binary replaced by stub."""
import hashlib,json,pathlib,shutil,subprocess,sys,time
R=pathlib.Path(__file__).resolve().parent
C=R/'dry_content_smoke_v2'
C.mkdir(exist_ok=False)
PAYLOAD=('worker_native.py','native_analysis.py','assert_T17.py','stub_native.py','t17b_manifest.json','t17b_stage.tar.gz','t17b_budget.json')
for n in PAYLOAD[:-1]:shutil.copy2(R/n,C/n)
plan=json.loads((R/'SESSION_PLAN.json').read_text())
cut=time.time()+.6*3600/5.4-90
(C/'t17b_budget.json').write_text(json.dumps({'mode':'smoke','fixture':True,'work_deadline':cut,
 'steps_per_T':plan['steps_per_T'],'steps_per_second':plan['steps_per_second'],
 'per_case_overhead_s':30,'teardown_s':60})+'\n')
assert set(p.name for p in C.iterdir())==set(PAYLOAD)
with (R/'DRY_WORKER_NATIVE_v2.log').open('x') as log:
 proc=subprocess.Popen([sys.executable,str(C/'worker_native.py')],cwd=C,env={**__import__('os').environ,'T17_CONTENT':str(C)},stdout=log,stderr=subprocess.STDOUT)
 done=False
 while proc.poll() is None:
  o=C/'t17b/out';hand=o/'t15_s1_handoff.json'
  if hand.exists() and not done:
   hashes=json.loads(hand.read_text())['sha256']
   if all((o/n).exists() and hashlib.sha256((o/n).read_bytes()).hexdigest()==h
          and (o/(n+'.sha256')).read_text().strip()==h for n,h in hashes.items()):
    (o/'t15_s1.ack.json').write_text(json.dumps(hashes)+'\n');done=True
  time.sleep(.2)
 rc=proc.wait()
assert rc==0 and done,(rc,done)
log=(R/'DRY_WORKER_NATIVE_v2.log').read_text()
margin=[float(line.split()[2]) for line in log.splitlines() if line.startswith('BUDGET_MARGIN')]
assert len(margin)==1 and margin[0]>0,margin
assert json.loads((C/'t17b/out/smoke_pipeline.json').read_text())['finite']
print('REAL_WORKER_STUB_ONLY_PASS','MARGIN_S',margin[0],'SHA_ACK',done,'EXIT',rc)
