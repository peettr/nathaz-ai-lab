import json
from pathlib import Path
P=Path(__file__).parent
files=[P/'docling_progress.jsonl']+[P/f'docling_{k}.jsonl' for k in ['FG72MNN8','L3RKLLUC','LLMUL7GY','NF6S3H9N','SDI6BHAF']]
rows=[json.loads(s) for f in files for s in f.read_text().splitlines()]
ids=[x['id'] for x in rows];assert len(ids)==25 and len(set(ids))==25,ids
rows.sort(key=lambda x:int(x['id'][1:]));expected={x['id'] for x in map(json.loads,(P/'eval_set_v3.jsonl').read_text().splitlines()) if x['group']=='B'}
assert set(ids)==expected
(P/'b_docling.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
print('COMPLETE B DOCLING',len(rows))
