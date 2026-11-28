#!/usr/bin/env python3
"""PAYLOAD-only real worker; replace only solver binary, exercise six-case ACK."""
import hashlib,json,pathlib,shutil,subprocess,sys,time,os
R=pathlib.Path(__file__).resolve().parent
C=R/'dry_content_v4';C.mkdir(exist_ok=False)
PAYLOAD=('worker_native.py','native_analysis.py','assert_T17.py','stub_native.py','t17b_manifest.json','t17b_stage.tar.gz','t17b_budget.json')
for n in PAYLOAD[:-1]:shutil.copy2(R/n,C/n)
plan=json.loads((R/'SESSION_PLAN.json').read_text())
cut=time.time()+3.5*3600/5.4-90
(C/'t17b_budget.json').write_text(json.dumps({'mode':'production','fixture':True,'work_deadline':cut,'steps_per_T':400,'steps_per_second':plan['steps_per_second'],'per_case_overhead_s':30,'teardown_s':90})+'\n')
assert {p.name for p in C.iterdir()}==set(PAYLOAD)
with (R/'DRY_WORKER_v4.log').open('x') as log:
 proc=subprocess.Popen([sys.executable,str(C/'worker_native.py')],cwd=C,env={**os.environ,'T17_CONTENT':str(C)},stdout=log,stderr=subprocess.STDOUT)
 labels=('t15_s1','t15_s2','t4_s1','t4_s2','bounce_s1','bounce_s2');acks=[]
 while proc.poll() is None:
  out=C/'t17b/out'
  if len(acks)<6:
   label=labels[len(acks)];manifest=out/(label+'_handoff.json')
   if manifest.exists():
    hashes=json.loads(manifest.read_text())['sha256']
    if all((out/n).exists() and hashlib.sha256((out/n).read_bytes()).hexdigest()==h and (out/(n+'.sha256')).read_text().strip()==h for n,h in hashes.items()):
     (out/(label+'.ack.json')).write_text(json.dumps(hashes)+'\n');acks.append(label)
  time.sleep(.15)
 rc=proc.wait()
lines=(R/'DRY_WORKER_v4.log').read_text().splitlines()
margin=[float(line.split()[2]) for line in lines if line.startswith('BUDGET_MARGIN')]
assert rc==0 and acks==list(labels) and len(margin)==6 and min(margin)>0,(rc,acks,margin,lines[-15:])
for label in labels:
 r=json.loads((C/'t17b/out'/(label+'_case.json')).read_text())
 assert len(r['blocks'])==4 and len(r['profile_u'])==64 and r['stress']['tau_x_time_mean']>0
 if label.endswith('s2'):assert len(r['v0_attempts'])==2
 else:assert len(r['v0_attempts'])==1
assert json.loads((C/'t17b/out/run.done').read_text())['verified']==list(labels)
(R/'DRY_PASS.json').write_text(json.dumps({'cases':acks,'min_margin_s':min(margin),'first_v0_branches':['pass','extend_then_pass'],'real_worker':True,'solver_only_stubbed':True},indent=2)+'\n')
print('DRY_PASS',json.dumps(json.loads((R/'DRY_PASS.json').read_text())))
