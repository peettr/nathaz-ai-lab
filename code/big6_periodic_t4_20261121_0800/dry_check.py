#!/usr/bin/env python3
"""Real worker fixture with only solver swapped; never a CFD result."""
from pathlib import Path
import os,sys,time,subprocess,hashlib,json,shutil
R=Path(__file__).resolve().parent; C=R/'dry_content_t4_v4';C.mkdir(exist_ok=False)
files=('worker_native.py','native_analysis.py','analyze_longspin.py','assert_T17.py','stub_native.py','t17b_manifest.json','t17b_stage.tar.gz')
for n in files:shutil.copy2(R/n,C/n)
(C/'t17b_budget.json').write_text(json.dumps({'mode':'production','fixture':True,'work_deadline':time.time()+330,'steps_per_T':400,'steps_per_second':{'t4':162},'per_case_overhead_s':20,'teardown_s':90})+'\n')
labels=('t4_s1','t4_s2');acks=[];log=R/'DRY_WORKER_T4_v4.log'
with log.open('x') as f:
 proc=subprocess.Popen([shutil.which('python3.10'),str(C/'worker_native.py')],cwd=C,env={**os.environ,'T17_CONTENT':str(C),'T17_TEST_NX':'32','T17_TEST_NY':'16'},stdout=f,stderr=subprocess.STDOUT)
 while proc.poll() is None:
  o=C/'t17b/out'
  if len(acks)<2:
   label=labels[len(acks)];p=o/(label+'_handoff.json')
   if p.is_file():
    h=json.loads(p.read_text())['sha256']
    if all((o/n).exists() and hashlib.sha256((o/n).read_bytes()).hexdigest()==v and (o/(n+'.sha256')).read_text().strip()==v for n,v in h.items()):
     (o/(label+'.ack.json')).write_text(json.dumps(h)+'\n');acks.append(label)
  time.sleep(.1)
rc=proc.wait(); lines=log.read_text().splitlines()
assert rc==0 and acks==list(labels),(rc,acks,lines[-20:])
for label in labels:
 o=C/'t17b/out';case=json.loads((o/(label+'_case.json')).read_text());windows=json.loads((o/(label+'_windows.json')).read_text())
 assert len(case['profile_u'])==64 and len(case['blocks'])==4 and case['stress']['tau_x_time_mean']>0
 assert len(case['v0_attempts'])==(2 if label.endswith('s2') else 1)
 assert len(windows)>=3 and all('S3_max_abs_difference' in w for w in windows)
assert json.loads((C/'t17b/out/run.done').read_text())['verified']==list(labels)
(R/'DRY_PASS_T4.json').write_text(json.dumps({'verified':acks,'windows':{x:len(json.loads((C/'t17b/out'/(x+'_windows.json')).read_text())) for x in labels},'solver_only_stubbed':True},indent=2)+'\n')
print('DRY_PASS_T4', (R/'DRY_PASS_T4.json').read_text())
