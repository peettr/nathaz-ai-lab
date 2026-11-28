#!/usr/bin/env python3
"""T02 probe R1 generation, two randomized blocks; no scientific compute.

Claude is intentionally excluded if weekly remaining <20%; see quota gate file.
Each invocation is a fresh tool-free conversation from approved QA entry points.
"""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import time
from datetime import datetime
from zoneinfo import ZoneInfo

BASE=Path(__file__).resolve().parents[1]
PROBE=Path(__file__).resolve().parent
SYS=Path('./22_Lab/06_Logs/l22_6/sessions/system.txt')
SEED=22060220261127
TZ=ZoneInfo('America/New_York')

def stamp():return datetime.now(TZ).isoformat()

def one(model,condition,block):
    identity=f'{model}_{condition}_b{block}'
    d=PROBE/identity
    d.mkdir(exist_ok=False)
    prompt=BASE/'prompts'/f'T02_{condition}.txt'
    if model=='gpt':
        cmd=[str(Path.home()/'bin/rc-model-qa'),'--caller','ideas-claude','--label','L22.6',
             '--model','astra','--system',str(SYS),'--prompt',str(prompt),'--out',str(d/'R1.json')]
    else:
        (d/'Q1.jsonl').write_text(json.dumps({'id': identity, 'prompt':prompt.read_text()},ensure_ascii=False)+'\n')
        cmd=['rc-gemini-batch','--in',str(d/'Q1.jsonl'),'--out',str(d/'A1.jsonl'),
             '--model','gemini-3.8-flash-high','--system',str(SYS),'-j','1',
             '--timeout','1800','--retries','0','--archive-label','L22.6','--tag','L22.6-T02']
    records=[]
    for attempt in (1,2):
        start=stamp()
        try:
            proc=subprocess.run(cmd,capture_output=True,text=True,stdin=subprocess.DEVNULL,timeout=1800)
            status='completed';rc=proc.returncode;log=proc.stdout+'\n'+proc.stderr
        except subprocess.TimeoutExpired as exc:
            status='censored';rc=None;log=(exc.stdout or b'').decode(errors='replace') if isinstance(exc.stdout,bytes) else (exc.stdout or '')
        (d/f'R1_attempt{attempt}.log').write_text(log)
        records.append({'attempt':attempt,'started_at':start,'ended_at':stamp(),'status':status,'exit_code':rc,
                        'raw_path':str(d/('R1.json' if model=='gpt' else 'A1.jsonl')),
                        'model_requested':'gpt-6-astra' if model=='gpt' else 'gemini-3.8-flash-high'})
        if status!='censored':break
    (d/'attempts.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
    return {'id':identity,'records':records}

def main():
    for condition,prefix in [('N','8a16b035'),('W','bae5fd03')]:
        digest=hashlib.sha256((BASE/'prompts'/f'T02_{condition}.txt').read_bytes()).hexdigest()
        assert digest.startswith(prefix),(condition,digest)
    assert SYS.read_text().strip()=='请完整作答。'
    rng=random.Random(SEED)
    for block in (1,2):
        cells=[(model,cond,block) for model in ('gpt','gemini') for cond in ('W','N')]
        rng.shuffle(cells)
        (PROBE/f'block{block}_order.json').write_text(json.dumps({'block':block,'seed':SEED,
          'claude_skipped':'quota cached 82% used, remaining 18% (<20%)',
          'order':[f'{m}_{c}_b{b}' for m,c,b in cells], 'started_at':stamp()},ensure_ascii=False,indent=2)+'\n')
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures=[pool.submit(one,*cell) for cell in cells]
            for f in concurrent.futures.as_completed(futures):
                try: row=f.result()
                except Exception as exc: row={'error':str(exc),'recorded_at':stamp()}
                with (PROBE/'generation_progress.jsonl').open('a') as out:
                    out.write(json.dumps(row,ensure_ascii=False)+'\n')
        print(json.dumps({'block':block,'completed_at':stamp()},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
