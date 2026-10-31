import json
from pathlib import Path
import score
P=Path(__file__).parent
score.items={r['id']:r for r in map(json.loads,(P/'eval_set_v2.jsonl').read_text().splitlines())}
models={'keyword':[{**x,'response':json.dumps({'answer':score.baseline(x)},ensure_ascii=False)} for x in score.items.values() if x['group'] in 'AC']}
claude={r['id']:r for r in map(json.loads,(P/'claude_responses.jsonl').read_text().splitlines())}
claude.update({r['id']:r for r in map(json.loads,(P/'claude_revised.jsonl').read_text().splitlines())})
models['Claude Sonnet']=list(claude.values())
for name in ['8b','30b']:
 f=P/f'{name}_responses.json'
 if not f.exists():continue
 data=json.loads(f.read_text())['rows']; override=P/f'{name}_revised.json'
 if override.exists():
  d={r['id']:r for r in data};d.update({r['id']:r for r in json.loads(override.read_text())['rows']});data=list(d.values())
 models[name]=data
print(json.dumps([r for name,rows in models.items() for r in score.summary(name,rows)],ensure_ascii=False,indent=2))
