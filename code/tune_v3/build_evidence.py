"""Read-only verification of 11 frozen tuning groups, then exclusive v3 artifacts.
Run only after tune_v3 completed with exit 0 and copied results hash-checked.
"""
import json, statistics, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
HERE=ROOT/'tune_v3'
OBJECTS=['131','252','424','505','657','812','896','1055']
PRIOR=0.057017+1.7469171004680943+2.2594278330
FAILED_SCORE_RESERVE=.1  # conservative charge for failed scoring_v1; reconcile actual if available
ARM_A_PENDING_RESERVE=8.0  # job 1747999: 4 slots x 2 h, verify live before gate

def main():
    elapsed=json.loads((HERE/'results_1748430/tuning_v3_elapsed.json').read_text())['elapsed_core_h']
    assert 0<elapsed<6.
    groups=[]
    for idx in range(11):
        folder=(ROOT/'tune_v1/results_1747115/tune_v1' if idx<4 else ROOT/'tune_v2/results_1747555/tune_v2' if idx<8 else HERE/'results_1748430')
        rows=[json.loads(s) for s in (folder/f'group_{idx:02d}.jsonl').read_text().splitlines() if s]
        assert len(rows)==48 and len({(r['object'],r['event'],r['seed']) for r in rows})==48
        assert all(r['wall_s']>0 for r in rows)
        summary=json.loads((folder/f'group_{idx:02d}_summary.json').read_text())
        med={o:statistics.median(r['S'] for r in rows if str(r['object'])==o) for o in OBJECTS}
        assert all(abs(v-summary['object_median_S'][o])<1e-12 for o,v in med.items())
        score=statistics.median(med.values())
        assert abs(score-summary['median_object_S'])<1e-12
        worst=max(r['wall_s'] for r in rows)
        scoring=1.2*worst*864/3600
        total=PRIOR+FAILED_SCORE_RESERVE+elapsed+ARM_A_PENDING_RESERVE+scoring
        groups.append({'group':idx,'hyper':summary['hyper'],'object_median_S':med,
                       'median_object_S':score,'max_sequence_wall_s':worst,
                       'scoring_est_core_h':scoring,'projected_total_core_h':total,
                       'eligible':total<=30})
    eligible=[g for g in groups if g['eligible']]
    assert eligible,'no group meets budget; manual halt'
    winner=min(eligible,key=lambda g:(g['median_object_S'],g['group']))
    outside=[g for g in groups if not g['eligible'] and g['median_object_S']<=.95*winner['median_object_S']]
    budget={'prior_core_h':PRIOR,'failed_scoring_reserve_h':FAILED_SCORE_RESERVE,
            'arm_a_pending_reserve_h':ARM_A_PENDING_RESERVE,
            'new_tuning_core_h':elapsed,'project_used_core_h':PRIOR+FAILED_SCORE_RESERVE+elapsed+ARM_A_PENDING_RESERVE,
            'winner_group':winner['group'],'winner_worst_sequence_wall_s':winner['max_sequence_wall_s'],
            'scoring_est_core_h_20pct':winner['scoring_est_core_h'],
            'projected_total_core_h':winner['projected_total_core_h'],
            'outside_improvement_5pct_groups':[g['group'] for g in outside],
            'scoring_gate_pass':not outside and winner['projected_total_core_h']<=30,
            'formula':'prior + failed scoring reserve + tune_v3 elapsed + armA pending 4 slots*2h + 1.2*max observed sequence wall_s*864/3600'}
    lines=['# 臂 B 十一组八对象中位 S（调参集）','',
           '数据源：CRC 调参作业原始 JSONL；本地快照 tune_v1/results_1747115、tune_v2/results_1747555、tune_v3/。每组 48 序列，每对象六条取中位，再对八对象取中位。','',
           '|组 (W秒/lr/steps)|'+'|'.join(OBJECTS)+'|八对象中位 S|最慢单序列 s|预计总核·时|预算内|',
           '|---|'+'---:|'*11+'---|']
    for g in groups:
        h=g['hyper']
        lines.append(f"|{g['group']} ({h['W']:g}/{h['lr']:g}/{h['steps']})|"+
            '|'.join(f"{g['object_median_S'][o]:.9f}" for o in OBJECTS)+
            f"|{g['median_object_S']:.9f}|{g['max_sequence_wall_s']:.6f}|{g['projected_total_core_h']:.6f}|{'是' if g['eligible'] else '否'}|")
    lines+=['',f"预算前置已用 {PRIOR:.9f} 核·时，失败评分保守预留 {FAILED_SCORE_RESERVE:.3f} 核·时；臂A在途承诺 {ARM_A_PENDING_RESERVE:.3f} 核·时；新调参实耗 {elapsed:.9f} 核·时。",
            f"预算内最佳组 {winner['group']}：{PRIOR:.9f}+{FAILED_SCORE_RESERVE:.3f}+{ARM_A_PENDING_RESERVE:.3f}+{elapsed:.9f}+1.2×{winner['max_sequence_wall_s']:.6f}×864/3600={winner['projected_total_core_h']:.9f} 核·时。",
            f"预算外超过5%改善组：{[g['group'] for g in outside]}。",'']
    table=HERE/'object_median_S_11groups.md';assert not table.exists()
    with table.open('x') as f:f.write('\n'.join(lines))
    bpath=HERE/'budget_v3.json';assert not bpath.exists()
    with bpath.open('x') as f:json.dump(budget,f,indent=2)
    print('BUDGET',json.dumps(budget))
    if budget['scoring_gate_pass']:
        frozen=ROOT/'frozen_config_v3.json'
        assert not frozen.exists()
        with frozen.open('x') as f:json.dump({'method':'G','hyper':winner['hyper'],'group':winner['group'],
            'selection':'lowest median of eight object medians among budget-eligible 11 groups',
            'source':'tune_v1 + tune_v2 + tune_v3 verified group JSONL',
            'scoring_set_run_at_freeze':False},f,indent=2)
        print('FROZEN_SHA256',hashlib.sha256(frozen.read_bytes()).hexdigest())
    else:print('STOP no freeze, no scoring due to 5 percent outside-budget improvement')
if __name__=='__main__':main()
