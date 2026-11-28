import concurrent.futures, json, subprocess, time, sys, os
from pathlib import Path
OUT=Path(__file__).parent;items=[json.loads(s) for s in (OUT/'eval_set.jsonl').read_text().splitlines()]
# Exactly the user prompt (no source/answer); no tools or workspace context supplied.
def one(x):
 t=time.monotonic(); cmd=['claude','-p','--no-session-persistence','--tools','','--output-format','json','--model','sonnet']
 try:
  p=subprocess.run(cmd,input=x['prompt'],text=True,capture_output=True,timeout=180,cwd=str(OUT))
  if p.returncode: return {'id':x['id'],'error':p.stderr[-600:],'elapsed_s':time.monotonic()-t}
  j=json.loads(p.stdout);return {'id':x['id'],'group':x['group'],'response':j.get('result',''),'usage':j.get('usage',{}),'cost_usd':j.get('total_cost_usd'),'modelUsage':j.get('modelUsage',{}),'elapsed_s':time.monotonic()-t,'error':j.get('is_error',False)}
 except Exception as e:return {'id':x['id'],'error':str(e),'elapsed_s':time.monotonic()-t}
start=time.monotonic();done={}
for x in (OUT/'claude_responses.jsonl').read_text().splitlines() if (OUT/'claude_responses.jsonl').exists() else []:
 try:r=json.loads(x);done[r['id']]=r
 except:pass
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
 for r in ex.map(one,[x for x in items if x['id'] not in done]):
  with (OUT/'claude_responses.jsonl').open('a') as f:f.write(json.dumps(r,ensure_ascii=False)+'\n')
  print(r['id'],'error',r.get('error'),round(r['elapsed_s'],1),'elapsed',round(time.monotonic()-start,1),flush=True)
print('COMPLETE',flush=True)
