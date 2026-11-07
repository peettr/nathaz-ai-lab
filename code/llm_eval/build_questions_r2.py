import json
from pathlib import Path
p=Path(__file__).parent
items=[json.loads(x) for x in (p/'eval_set_r2.jsonl').read_text().splitlines()]
out=p/'gemini_questions_r2.jsonl'
assert not out.exists()
out.write_text(''.join(json.dumps({'id':x['id'],'prompt':x['prompt']},ensure_ascii=False)+'\n' for x in items))
print(len(items),out)
