#!/usr/bin/env python3
"""Post hoc Wood-36 report, computed only from original and extension JSON archives."""
import hashlib, json, statistics, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import render_A170_2 as base
HERE=Path(__file__).resolve().parent
OLD=HERE.parents[0]/'crc_loads_v1'/'results_1741469.tar.gz'
NEW=HERE/'results_wood36.tar.gz'

def main():
    old=base.read_archive(OLD); new=base.read_archive(NEW)
    assert len([k for k in new if k.startswith('P1_wood_') and k.endswith('.json')])==48
    expected=[f'P1_wood_s{s}_{g}.json' for s in range(1313,1337) for g in ('G1','G2Lc')]
    assert set(expected).issubset(new)
    assert not set(old).intersection(expected)
    rows=dict(old,**new)
    wood=base.cmp(rows,('wood','G2Lc'),base.SEEDS)
    power=base.cmp(rows,('power','G2Lc'),base.SEEDS)
    def lead(profile):
        values=[]
        for s in base.SEEDS:
            a=rows[f'P1_{profile}_s{s}_G1.json']
            b=rows[f'P1_{profile}_s{s}_G2Lc.json']
            if a.get('returncode')==b.get('returncode')==0 and max(a['yaw_rate_max_deg_s'],b['yaw_rate_max_deg_s'])<=.31 and a['trigger_abs_s'] is not None and b['trigger_abs_s'] is not None:
                values.append(a['trigger_abs_s']-b['trigger_abs_s'])
        return {'n':len(values),'median_s':statistics.median(values) if values else None,'range_s':[min(values),max(values)] if values else None,'per_valid_pair_s':values}
    summary={p:{g:{'n_success':sum(rows[f'P1_{p}_s{s}_{g}.json'].get('returncode')==0 for s in base.SEEDS),'rate_median_deg_s':statistics.median(rows[f'P1_{p}_s{s}_{g}.json']['yaw_rate_max_deg_s'] for s in base.SEEDS),'rate_max_deg_s':max(rows[f'P1_{p}_s{s}_{g}.json']['yaw_rate_max_deg_s'] for s in base.SEEDS),'rate_over_0p31':sum(rows[f'P1_{p}_s{s}_{g}.json']['yaw_rate_max_deg_s']>.31 for s in base.SEEDS)} for g in ('G1','G2Lc')} for p in ('power','wood')}
    sensitivity=wood['a']!=power['a'] or wood['b']!=power['b']
    result={'design':'Wood extension chosen after observing first 12 Wood median; frozen n=36 interval reused post hoc, not a preregistered Wood-36 test', 'wood_vs_G1':wood,'power_vs_G1':power,'profile_sensitive_by_verdict':sensitivity,'lead_time_G1_minus_G2Lc_s':{p:lead(p) for p in ('power','wood')},'group_summary':summary,'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (OLD,NEW)},'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (HERE/'metrics_A170_2_wood36.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    lines=['# A170② P1 Wood 36种子事后扩样','', '看过原Wood 12对中位后追加24种子；沿用冻结次序统计判据，但不是预注册Wood 36种子试验。旧JSON未替换。','', '| 廓线 | 指标 | 有效对 | 不判 | 中位降幅 % | 95% [R(12),R(25)] % | 判定 |','|---|---|---:|---:|---:|---|---|']
    for p,c in [('power',power),('wood',wood)]:
        for k in base.FIELDS:
            x=c['metrics'][k]; ci=x['interval_R12_R25_pct']; ci_text='—' if ci is None else f'[{ci[0]:.3f},{ci[1]:.3f}]'
            med='—' if x['median_pct'] is None else f"{x['median_pct']:.3f}"
            lines.append(f"| {p} | {k} | {c['n_valid']} | {c['n_not_judged']} | {med} | {ci_text} | {x['verdict']} |")
        lines.append(f"| {p} | (a)/(b) | {c['n_valid']} | {c['n_not_judged']} | — | — | {c['a']}/{c['b']} |")
    lines+=['',f"廓线判定词是否不同：{'是，对廓线假设敏感' if sensitivity else '否'}。",'','| 廓线/组 | 成功 | 1 s偏航割线中位/最大 (°/s) | >0.31次数 |','|---|---:|---:|---:|']
    for p,groups in summary.items():
        for g,v in groups.items():lines.append(f"| {p}/{g} | {v['n_success']} | {v['rate_median_deg_s']:.5f}/{v['rate_max_deg_s']:.5f} | {v['rate_over_0p31']} |")
    lines+=['','| 廓线 | G1−G2Lc触发提前量中位 (s) | 范围 (s) | 有效数 |','|---|---:|---:|---:|']
    for p in ('power','wood'):
        v=result['lead_time_G1_minus_G2Lc_s'][p];span='—' if v['range_s'] is None else f"{v['range_s'][0]:.3f}至{v['range_s'][1]:.3f}"
        lines.append(f"| {p} | {v['median_s']} | {span} | {v['n']} |")
    lines+=['',f"制表脚本 SHA256：{result['script_sha256']}",f"新增检查点 SHA256：{result['source_sha256'][str(NEW)]}"]
    (HERE/'RESULTS_A170_2_wood36.md').write_text('\n'.join(lines)+'\n')
    print('rendered',wood['n_valid'],power['n_valid'])
if __name__=='__main__':main()
