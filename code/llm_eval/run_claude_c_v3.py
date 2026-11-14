import concurrent.futures,json,subprocess,time
from pathlib import Path
P=Path(__file__).parent;rows=[json.loads(s) for s in (P/'eval_set_v3.jsonl').read_text().splitlines() if json.loads(s)['group']=='C']
def one(x):
 t=time.monotonic();p=subprocess.run(['claude','-p','--no-session-persistence','--tools','','--output-format','json','--model','sonnet'],input=x['prompt'],text=True,capture_output=True,timeout=180,cwd=str(P));j=json.loads(p.stdout);return {'id':x['id'],'group':'C','response':j.get('result',''),'usage':j.get('usage',{}),'cost_usd':j.get('total_cost_usd'),'elapsed_s':time.monotonic()-t}
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
 results=list(ex.map(one,rows))
(P/'claude_c_v3.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in results));print('COMPLETE',len(results),flush=True)
