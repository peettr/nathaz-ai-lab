import json
from pathlib import Path
import score
P=Path(__file__).parent;score.items={r['id']:r for r in map(json.loads,(P/'eval_set_v3.jsonl').read_text().splitlines())}
models={'keyword':[{**x,'response':json.dumps({'answer':score.baseline(x)},ensure_ascii=False)} for x in score.items.values() if x['group'] in 'AC']}
claude={r['id']:r for r in map(json.loads,(P/'claude_responses.jsonl').read_text().splitlines())}
for fn in ['claude_revised.jsonl','claude_c_v3.jsonl']:
 claude.update({r['id']:r for r in map(json.loads,(P/fn).read_text().splitlines())})
models['Claude Sonnet']=list(claude.values())
for name in ['8b','30b']:
 f=P/f'{name}_responses.json'
 if not f.exists():continue
 data={r['id']:r for r in json.loads(f.read_text())['rows']}
 for fn in [f'{name}_revised.json',f'{name}_c_v3.json']:
  if (P/fn).exists():data.update({r['id']:r for r in json.loads((P/fn).read_text())['rows']})
 models[name]=list(data.values())
print(json.dumps([r for name,rows in models.items() for r in score.summary(name,rows)],ensure_ascii=False,indent=2))
