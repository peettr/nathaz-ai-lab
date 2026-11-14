#!/usr/bin/env python3
"""Run each frozen query exactly once; save raw CLI output and command status."""
import hashlib, json, os, pathlib, subprocess, sys, time
Q = pathlib.Path('./22_Lab/06_Logs/figure_kb/review_0242/questions_m20.jsonl')
O = pathlib.Path(__file__).resolve().parent
EXPECTED='b1209f27880b87589f4131eaf9bd7276d11a8d0e850b49b795ec502cf8fa158e'
assert hashlib.sha256(Q.read_bytes()).hexdigest()==EXPECTED
questions=[json.loads(x) for x in Q.read_text().splitlines()]
assert len(questions)==20
ctx=os.environ['RC_CTX']
log=O/'query_log.jsonl'
completed={(json.loads(line)['id'],json.loads(line)['mode']) for line in log.read_text().splitlines()} if log.exists() else set()
for item in questions:
    for mode, key in [('zh','q'),('en','q_en')]:
        if (item['id'],mode) in completed:
            continue
        cmd=['rc-kb','--ctx',ctx,'figs',item[key],'-n','5']
        start=time.time()
        try:
            p=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=180)
            result={'id':item['id'],'mode':mode,'exit_code':p.returncode,'seconds':round(time.time()-start,2),'stdout':p.stdout,'stderr':p.stderr}
        except subprocess.TimeoutExpired as e:
            result={'id':item['id'],'mode':mode,'exit_code':'TIMEOUT','seconds':round(time.time()-start,2),'stdout':(e.stdout or b'').decode(errors='replace') if isinstance(e.stdout,bytes) else (e.stdout or ''),'stderr':str(e)}
        with log.open('a') as f: f.write(json.dumps(result,ensure_ascii=False)+'\n')
        (O/f"{item['id']}_{mode}.txt").write_text(result['stdout']+'\nSTDERR: '+result['stderr'])
        print(item['id'],mode,result['exit_code'],result['seconds'],flush=True)
        if result['exit_code']!=0:
            print('STOP ON FAILURE; do not rerun a frozen query',flush=True)
            sys.exit(2)
