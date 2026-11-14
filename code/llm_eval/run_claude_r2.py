"""Claude CLI: independent one-question calls, checkpoint each, never leak labels."""
import concurrent.futures,json,subprocess,time
from pathlib import Path
p=Path(__file__).parent;items=[json.loads(x) for x in (p/'eval_set_r2.jsonl').read_text().splitlines()];out=p/'claude_answers_r2.jsonl';sys=(p/'system_r2.txt').read_text().strip()
done={}
if out.exists():
 for s in out.read_text().splitlines():
  try:
   r=json.loads(s)
   if not r.get('error'):done[r['id']]=r
  except Exception:pass
def one(x):
 t=time.monotonic();cmd=['claude','-p','--no-session-persistence','--tools','','--output-format','json','--model','sonnet','--append-system-prompt',sys]
 try:
  v=subprocess.run(cmd,input=x['prompt'],text=True,capture_output=True,timeout=240,cwd=str(p))
  if v.returncode:return {'id':x['id'],'error':v.stderr[-800:] or v.stdout[-800:],'elapsed_s':time.monotonic()-t}
  q=json.loads(v.stdout)
  return {'id':x['id'],'response':q.get('result',''),'usage':q.get('usage',{}),'cost_usd':q.get('total_cost_usd'),'modelUsage':q.get('modelUsage',{}),'elapsed_s':time.monotonic()-t,'error':q.get('is_error',False)}
 except Exception as e:return {'id':x['id'],'error':str(e),'elapsed_s':time.monotonic()-t}
t=time.monotonic()
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
 for n,r in enumerate(ex.map(one,[x for x in items if x['id'] not in done]),1):
  with out.open('a') as f:f.write(json.dumps(r,ensure_ascii=False)+'\n')
  if n%10==0 or r.get('error'):print('CLAUDE',n,r['id'],'err',str(r.get('error'))[:60],'elapsed',round(time.monotonic()-t,1),flush=True)
print('CLAUDE COMPLETE',len(items),flush=True)
