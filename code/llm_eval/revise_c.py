import json
from pathlib import Path
P=Path(__file__).parent
rows=[json.loads(s) for s in (P/'eval_set_v2.jsonl').read_text().splitlines()]
for r in rows:
 if r['group']=='C':
  text=r['prompt'].split('描述：',1)[1]
  r['prompt']='根据 NOAA Storm Events 事件描述判别类型。四个选项为 Thunderstorm Wind、High Wind、Strong Wind、其他。必须只选择其中一个，不得照抄选项列表。只输出含单个 answer 字段的 JSON 对象，例如 {"answer":"High Wind"}。\n描述：'+text
assert len(rows)==100
(P/'eval_set_v3.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
print('v3 C prompt corrected; original and v2 preserved')
