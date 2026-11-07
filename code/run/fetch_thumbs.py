#!/usr/bin/env python3
"""Fetch each frozen top-five thumbnail once, preserving CLI responses."""
import json, pathlib, re, subprocess, os, sys
O=pathlib.Path(__file__).resolve().parent
rows=[json.loads(x) for x in (O/'query_log.jsonl').read_text().splitlines()]
assert len(rows)==40 and all(x['exit_code']==0 for x in rows)
found=[]
for row in rows:
    ids=re.findall(r'^\s*图号 ([a-f0-9]{24})\b',row['stdout'],re.M)
    assert len(ids)==5,(row['id'],row['mode'],ids)
    found.extend(ids)
ids=list(dict.fromkeys(found))
log=O/'thumb_log.jsonl'
seen={json.loads(x)['fig_id'] for x in log.read_text().splitlines()} if log.exists() else set()
for i,fig_id in enumerate(ids,1):
    if fig_id in seen: continue
    cmd=['rc-kb','--ctx',os.environ['RC_CTX'],'figs','--thumb',fig_id]
    try:
        p=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=50)
        result={'fig_id':fig_id,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
    except subprocess.TimeoutExpired as e:
        result={'fig_id':fig_id,'exit_code':'TIMEOUT','stdout':'','stderr':str(e)}
    with log.open('a') as f: f.write(json.dumps(result,ensure_ascii=False)+'\n')
    print(i,len(ids),fig_id,result['exit_code'],flush=True)
    if result['exit_code']!=0:
        print('STOP; no automatic retry',flush=True);sys.exit(2)
print('unique thumbs',len(ids),flush=True)
