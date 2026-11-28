#!/usr/bin/env python3
"""PAYLOAD-only real-worker fixture; stub only executable."""
import hashlib,json,pathlib,shutil,subprocess,sys,time
R=pathlib.Path(__file__).resolve().parent; names=('worker_diag.py','remote_diag.py','diag_stage.tar.gz','diag_manifest.json','diag_budget.json')
c=R/'dry_content_sealed';c.mkdir(exist_ok=False)
for n in names[:-1]:shutil.copy2(R/n,c/n)
created=time.time();cut=created+0.3*3600/5.4-35
(c/'diag_budget.json').write_text(json.dumps({'mode':'fixture','work_deadline':cut})+'\n')
assert set(p.name for p in c.iterdir())==set(names)
print('PATH_PAYLOAD_MAP',json.dumps({'worker_diag.py':'PAYLOAD worker','diag_stage.tar.gz':'PAYLOAD archive -> stage','diag_manifest.json':'PAYLOAD hashes','diag_budget.json':'PAYLOAD deadline','remote_diag.py':'PAYLOAD launcher/ACK'}),flush=True)
print('BUDGET_ARITHMETIC',json.dumps({'cap_CU':0.3,'rate_CU_per_hour':5.4,'session_seconds':0.3*3600/5.4,'stop_reserve_s':35,'build_compile_s':45,'D5_s':40,'D6_s':40,'evidence_ack_s':20,'prelaunch_margin_s':cut-created-(45+40+40+20)}),flush=True)
with (R/'DRY_WORKER_sealed.log').open('x') as log:
 p=subprocess.Popen([sys.executable,str(c/'worker_diag.py'),'--content',str(c),'--stub',str(R/'stub_solver.py')],cwd=c,stdout=log,stderr=subprocess.STDOUT)
 seen=set()
 while p.poll() is None:
  o=c/'diag/out'
  for label in ('d5','d6'):
   hand=o/(label+'_handoff.json')
   if hand.exists() and label not in seen:
    hashes=json.loads(hand.read_text())['sha256']
    if all((o/n).exists() and hashlib.sha256((o/n).read_bytes()).hexdigest()==h and (o/(n+'.sha256')).read_text().strip()==h for n,h in hashes.items()):
     (o/(label+'.ack.json')).write_text(json.dumps(hashes));seen.add(label);print('HOST_ACK',label,flush=True)
  time.sleep(.2)
 rc=p.wait()
lines=(R/'DRY_WORKER_sealed.log').read_text().splitlines();marks=[float(s.split('margin_s ')[1]) for s in lines if s.startswith('BUDGET_STAGE')]
print('WORKER_EXIT',rc,'ACK',sorted(seen),'MARGIN_MIN',min(marks) if marks else None,flush=True)
assert rc==0 and seen=={'d5','d6'} and marks and min(marks)>0 and (c/'diag/out/run.done').exists()
