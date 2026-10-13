import json,subprocess,time
from pathlib import Path
P=Path(__file__).parent
rows=[json.loads(s) for s in (P/'eval_set_v2.jsonl').read_text().splitlines() if json.loads(s)['id'] in ['D13','D14','D15']]
with (P/'claude_revised.jsonl').open('w') as f:
 for x in rows:
  t=time.monotonic();p=subprocess.run(['claude','-p','--no-session-persistence','--tools','','--output-format','json','--model','sonnet'],input=x['prompt'],text=True,capture_output=True,timeout=180,cwd=str(P));j=json.loads(p.stdout);r={'id':x['id'],'group':'D','response':j.get('result',''),'usage':j.get('usage',{}),'cost_usd':j.get('total_cost_usd'),'elapsed_s':time.monotonic()-t};f.write(json.dumps(r,ensure_ascii=False)+'\n');print(x['id'],r['response'],flush=True)
