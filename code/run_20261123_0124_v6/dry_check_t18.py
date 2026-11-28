from pathlib import Path
import os,time,subprocess,hashlib,json,shutil
R=Path(__file__).resolve().parent; C=R/'dry_content_t18';C.mkdir(exist_ok=False)
files=('worker_native.py','native_analysis.py','analyze_longspin.py','stub_t18.py','stub_native_original.py','t17b_manifest.json','t17b_stage.tar.gz')
for n in files:shutil.copy2(R/n,C/n)
(C/'t17b_budget.json').write_text(json.dumps({'mode':'production','fixture':True,'work_deadline':time.time()+13.1*3600/5.4-90,'steps_per_T':400,'steps_per_second':{g:162 for g in ('K1a','K1b','K2','K3a','K3b')},'per_case_overhead_s':20,'teardown_s':90})+'\n')
labels=tuple(g+'_s1' for g in ('K1a','K1b','K2','K3a','K3b'));acks=[];log=R/'DRY_WORKER_T18.log'
with log.open('x') as f:
 proc=subprocess.Popen([shutil.which('python3.10'),str(C/'worker_native.py')],cwd=C,env={**os.environ,'T17_CONTENT':str(C),'T17_TEST_NX':'32','T17_TEST_NY':'16'},stdout=f,stderr=subprocess.STDOUT)
 while proc.poll() is None:
  o=C/'t17b/out'
  if len(acks)<len(labels):
   label=labels[len(acks)];p=o/(label+'_handoff.json')
   if p.is_file():
    h=json.loads(p.read_text())['sha256']
    if all((o/n).exists() and hashlib.sha256((o/n).read_bytes()).hexdigest()==v and (o/(n+'.sha256')).read_text().strip()==v for n,v in h.items()):
     (o/(label+'.ack.json')).write_text(json.dumps(h)+'\n');acks.append(label)
  time.sleep(.1)
rc=proc.wait();lines=log.read_text().splitlines()
assert rc==0 and acks==list(labels),(rc,acks,lines[-20:])
assert json.loads((C/'t17b/out/run.done').read_text())['verified']==list(labels)
assert json.loads((C/'t17b/out/C0_verdict.json').read_text())['fixture_only']
(R/'DRY_PASS_T18.json').write_text(json.dumps({'verified':acks,'solver_only_stubbed':True,'c0_fixture_only':True},indent=2)+'\n')
print('DRY_PASS_T18',len(acks))
