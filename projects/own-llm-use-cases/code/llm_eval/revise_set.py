import json
from pathlib import Path
P=Path(__file__).parent
old=[json.loads(s) for s in (P/'eval_set.jsonl').read_text().splitlines()]
benchmark=Path('./16_PETW/02_Subprojects/Design_Load/outputs/GFF_Implementation_20260807/full_time_frequency_i3_benchmark_v1.json')
case=json.loads(benchmark.read_text())['cases']
for i,c in zip(range(13,16),case[4:7]):
 a,b=c['max_sigma_q'],c['max_sigma_x'];v=a/b
 for j,x in enumerate(old):
  if x['id']==f'D{i:02}':
   old[j]={'group':'D','id':x['id'],'prompt':f'候选计算器回归单点：最大广义荷载标准差 {a:.12g}，最大响应标准差 {b:.12g}。求前者除以后者的无量纲比值（至少 4 位小数）。仅答 JSON：{{"answer":数字}}。','answer':v,'source':str(benchmark)+f'#cases[{i-9}].max_sigma_q/max_sigma_x','unit':'1'}
assert len(old)==100 and len({x['id'] for x in old})==100
(P/'eval_set_v2.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in old))
print('new version preserves original; D13-15 revised')
