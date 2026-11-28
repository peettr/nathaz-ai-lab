import json,pathlib
p=pathlib.Path('/content/s2/incremental.jsonl')
for row in [json.loads(x) for x in p.read_text().splitlines() if x.strip()]:
 print({k:row.get(k) for k in ('unit_index','kind','seed','status','error','trace','elapsed_s')})
