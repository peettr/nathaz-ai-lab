import json, statistics, hashlib, shutil
from pathlib import Path
root=Path(__file__).resolve().parents[1]
v2=root/'tune_v2'
source=v2/'results_1747555'
summary=json.loads((source/'tune_v2/tuning_summary_8groups.json').read_text())
objects=['131','252','424','505','657','812','896','1055']
for g in summary['groups']:
    idx=g['group']
    path=(root/'tune_v1/results_1747115/tune_v1' if idx<4 else source/'tune_v2')/f'group_{idx:02}.jsonl'
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows)==48 and len({(r['object'],r['event'],r['seed']) for r in rows})==48
    for obj in objects:
        val=statistics.median(r['S'] for r in rows if str(r['object'])==obj)
        assert abs(val-g['object_median_S'][obj])<1e-12,(idx,obj,val)
    assert abs(statistics.median(g['object_median_S'].values())-g['median_object_S'])<1e-12
winner=min(summary['groups'],key=lambda g:(g['median_object_S'],g['group']))
assert winner==summary['chosen'] and winner['group']==6
budget=summary['budget']
assert abs(budget['prior_core_h']+budget['new_tuning_core_h']+1.2*winner['wall_s']/48*864/3600-budget['projected_total_core_h'])<1e-9
lines=['# 臂B 八组调参对象中位 S（作业 1747115 与 1747555）','','数据来源：CRC tune_v1/group_00..03.jsonl 与 tune_v2/group_04..07.jsonl；每格为对象在 2 调参事件 × 3 种子的中位 S，末列为八对象中位数；各组 48 行，逐行核对后生成。评分集此表生成时未运行。','','| 组 (W秒/lr/steps) | '+' | '.join(objects)+' | 八对象中位 S |','|---|'+'---:|'*9]
for g in summary['groups']:
    h=g['hyper']; vals=[f"{g['object_median_S'][o]:.9f}" for o in objects]
    lines.append(f"| {g['group']} ({h['W']:g}/{h['lr']:g}/{h['steps']}) | "+' | '.join(vals)+f" | {g['median_object_S']:.9f} |")
lines+=['',f"冻结组 {winner['group']}：W={winner['hyper']['W']:g} s，lr={winner['hyper']['lr']:g}，steps={winner['hyper']['steps']}。",f"预算（单槽）：{budget['prior_core_h']:.9f} + {budget['new_tuning_core_h']:.9f} + 1.2 × {winner['wall_s']:.9f}/48 × 864/3600 = {budget['projected_total_core_h']:.9f} 核·时（评分估算 {budget['scoring_est_core_h_20pct']:.9f}），低于 30 核·时。",'']
(v2/'object_median_S_8groups.md').write_text('\n'.join(lines))
target=root/'frozen_config_v2.json'
assert not target.exists()
shutil.copyfile(source/'frozen_config_v2.json',target)
print('winner',winner['group'],'rows',8*48,'budget',budget,'frozen_sha256',hashlib.sha256(target.read_bytes()).hexdigest())
