#!/usr/bin/env python3
"""Isolated PAYLOAD-only real-worker fixture; only solver binary stubbed."""
import hashlib,json,pathlib,shutil,subprocess,sys,time
R=pathlib.Path(__file__).resolve().parent
PAYLOAD=('worker_full.py','remote_io.py','assert_ledger.py','t17_stage.tar.gz','t17_manifest.json','t17_budget.json')
c=R/'dry_content';c.mkdir(exist_ok=False)
for n in PAYLOAD[:-1]:shutil.copy2(R/n,c/n)
# Actual production cut formula, including 90 s teardown reserve.
created=time.time();cut=created+1.5*3600/5.4-90
(c/'t17_budget.json').write_text(json.dumps({'mode':'fixture','work_deadline':cut})+'\n')
assert set(p.name for p in c.iterdir())==set(PAYLOAD)
print('PATH_PAYLOAD_MAP',json.dumps({'worker opens':{'worker_full.py':'PAYLOAD worker_full.py','assert_ledger.py':'PAYLOAD assert_ledger.py','t17_stage.tar.gz':'PAYLOAD t17_stage.tar.gz','t17_manifest.json':'PAYLOAD t17_manifest.json','t17_budget.json':'PAYLOAD t17_budget.json','extracted pack_stage':'derived from PAYLOAD archive'},'ACK':'derived by host'},indent=2),flush=True)
with (R/'DRY_WORKER.log').open('x') as log:
 p=subprocess.Popen([sys.executable,str(c/'worker_full.py'),'--content',str(c),'--stub',str(R/'stub_solver.py')],cwd=c,stdout=log,stderr=subprocess.STDOUT)
 seen=set();labels=('a1b','a3','a7','speed_bounce','speed_t4','speed_t15')
 while p.poll() is None:
  o=c/'t17/out'
  for label in labels:
   hand=o/(label+'_handoff.json')
   if hand.is_file() and label not in seen:
    hashes=json.loads(hand.read_text())['sha256']
    if not all((o/n).is_file() and hashlib.sha256((o/n).read_bytes()).hexdigest()==h and (o/(n+'.sha256')).read_text().strip()==h for n,h in hashes.items()):continue
    (o/(label+'.ack.json')).write_text(json.dumps(hashes));seen.add(label);print('HOST_ACK',label,flush=True)
  time.sleep(.2)
 rc=p.wait()
print('WORKER_EXIT',rc,'ACKS',list(seen),flush=True)
log=(R/'DRY_WORKER.log').read_text()
marks=[float(line.split('margin_s ')[1].split()[0]) for line in log.splitlines() if line.startswith('BUDGET_STAGE')]
assert marks and all(v>0 for v in marks),'production cut margin not positive'
print('PRODUCTION_CUT_MARGIN_MIN_S',min(marks),flush=True)
assert rc==0 and seen==set(labels) and (c/'t17/out/run.done').is_file()
