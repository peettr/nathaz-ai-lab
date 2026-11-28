#!/usr/bin/env python3
"""Execute actual worker in PAYLOAD-only sandbox, stub only the solver."""
import hashlib,json,os,pathlib,shutil,subprocess,sys,time
R=pathlib.Path(__file__).resolve().parent
PAYLOAD=('worker_B.py','assert_T17.py','t17b_stage.tar.gz','t17b_manifest.json','t17b_budget.json')
suffix=os.environ.get('T17_DRY_SUFFIX','')
c=R/('dry_content'+suffix);c.mkdir(exist_ok=False)
for n in PAYLOAD[:-1]:shutil.copy2(R/n,c/n)
plan=json.loads((R/'SESSION_PLAN.json').read_text())
created=time.time();cut=created+plan['budget_CU']*3600/plan['rate_CU_per_hour']-90
(c/'t17b_budget.json').write_text(json.dumps({'mode':'fixture','work_deadline':cut,'steps_per_T':plan['steps_per_T'],
    'steps_per_second':plan['steps_per_second'],'per_case_overhead_s':plan['per_case_overhead_s']})+'\n')
assert set(p.name for p in c.iterdir())==set(PAYLOAD)
labels=[g+'_s'+s for g in ('bounce','t4','t15') for s in ('1','2')]
logfile=R/('DRY_WORKER'+suffix+'.log')
with logfile.open('x') as log:
    env={**os.environ,'T17_B_FIXTURE':os.environ.get('T17_FIXTURE_PATH',str(R/'fixture_pipeline_only.json'))}
    p=subprocess.Popen([sys.executable,str(c/'worker_B.py'),'--content',str(c),'--stub',str(R/'stub_B.py')],
                       cwd=c,env=env,stdout=log,stderr=subprocess.STDOUT)
    done=set()
    while p.poll() is None:
        o=c/'t17b/out'
        for label in labels:
            hand=o/(label+'_handoff.json')
            if label in done or not hand.is_file():continue
            try:
                hashes=json.loads(hand.read_text())['sha256']
                if not all((o/n).is_file() and hashlib.sha256((o/n).read_bytes()).hexdigest()==h
                       and (o/(n+'.sha256')).read_text().strip()==h for n,h in hashes.items()):continue
            except (ValueError,OSError):continue
            (o/(label+'.ack.json')).write_text(json.dumps(hashes)+'\n');done.add(label)
            print('HOST_ACK',label,flush=True)
        time.sleep(.2)
    rc=p.wait()
print('WORKER_EXIT',rc,'ACKS',sorted(done),flush=True)
rows=logfile.read_text().splitlines()
margins=[float(row.split('PRODUCTION_CUT_MARGIN ')[1].split()[0]) for row in rows if row.startswith('PRODUCTION_CUT_MARGIN ')]
assert rc==0 and done==set(labels) and len(margins)==6 and min(margins)>0
result=json.loads((c/'t17b/out/T17_result.json').read_text())
assert result['group_verdicts']=={'bounce':'达标','t4':'达标','t15':'达标'}
print('PRODUCTION_CUT_MARGIN_MIN_S',min(margins),'SHA_ACK_6_OK',flush=True)
