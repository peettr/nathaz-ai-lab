"""Read-only source checks, budget-stop table for 11 tuning groups."""
import json, statistics
from pathlib import Path
R=Path(__file__).resolve().parents[1]
HERE=R/'tune_v3'
OBJECTS=['131','252','424','505','657','812','896','1055']
prior=.057017+1.7469171004680943+2.2594278330
elapsed=json.loads((HERE/'results_1748430/tuning_v3_elapsed.json').read_text())['elapsed_core_h']
reserve_failed=.1
reserve_a=8.
base=prior+elapsed+reserve_failed+reserve_a
out=[]
for i in range(11):
    folder=(R/'tune_v1/results_1747115/tune_v1' if i<4 else R/'tune_v2/results_1747555/tune_v2' if i<8 else HERE/'results_1748430')
    rows=[json.loads(s) for s in (folder/f'group_{i:02d}.jsonl').read_text().splitlines() if s]
    summary=json.loads((folder/f'group_{i:02d}_summary.json').read_text())
    assert len(rows)==48 and len({(r['object'],r['event'],r['seed']) for r in rows})==48
    med={o:statistics.median(r['S'] for r in rows if str(r['object'])==o) for o in OBJECTS}
    assert all(abs(med[o]-summary['object_median_S'][o])<1e-12 for o in OBJECTS)
    score=statistics.median(med.values())
    assert abs(score-summary['median_object_S'])<1e-12
    worst=max(r['wall_s'] for r in rows)
    est=1.2*worst*864/3600
    out.append((i,summary['hyper'],med,score,worst,est,base+est))
lines=['# 十一组调参预算止损核验','','数据来源：CRC 作业 1747115、1747555、1748430 的逐序列 JSONL（本地哈希核对副本）。每组48条；对象取2事件×3种子S中位，再对8对象取中位。最慢单序列为该组48条最大实测 wall_s。','',
'|组 (W/lr/steps)|'+'|'.join(OBJECTS)+'|八对象中位 S|最慢序列 s|评分估算核·时|全项目含承诺核·时|预算内|',
'|---|'+'---:|'*12+'---|']
for i,h,med,s,w,e,t in out:
    lines.append(f"|{i} ({h['W']:g}/{h['lr']:g}/{h['steps']})|"+'|'.join(f'{med[o]:.9f}' for o in OBJECTS)+f'|{s:.9f}|{w:.6f}|{e:.6f}|{t:.6f}|{"是" if t<=30 else "否"}|')
best=min(out,key=lambda v:(v[3],v[0]));eligible=[x for x in out if x[6]<=30]
lines+=['',f'已用估算 {prior:.9f} + 新调参实耗 {elapsed:.9f} + 失败评分预留 {reserve_failed:.3f} + 臂A在途4槽×2h承诺 {reserve_a:.3f} = {base:.9f} 核·时。',
       f'十一组预算内数量 {len(eligible)}；全组最低S组 {best[0]}，S={best[3]:.9f}，其预算= {base:.9f} + 1.2×{best[4]:.6f}×864/3600 = {best[6]:.9f} 核·时。',
       '预算内无可冻结组；不冻结、不评分。臂A在途承诺必须计入，不能把评分墙钟预计替代提交时h_rt资源承诺。','']
target=HERE/'object_median_S_11groups.md'
with target.open('x') as f:f.write('\n'.join(lines))
print('prior',prior,'elapsed',elapsed,'base',base,'eligible',len(eligible),'best',best[0],best[3],best[4],best[6]);print('table',target)
