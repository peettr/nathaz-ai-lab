#!/usr/bin/env python3
"""Read-only v10 ratio postprocess; never replace an existing artifact."""
import json
from pathlib import Path

DIR = Path(__file__).resolve().parent
SOURCE = DIR / 'metrics_A_v10_partial.json'
OUT_JSON = DIR / 'metrics_A_benefit_ratio_v10_partial.json'
OUT_MD = DIR / 'RESULTS_A_benefit_ratio_v10_partial.md'
FIELDS = {
    'tower_resultant_max_kNm': '塔底合成极值',
    'tower_fore_aft_absmax_kNm': '塔底前后向绝对极值',
    'tower_fore_aft_positive_max_kNm': '塔底前后向正峰',
    'tower_fore_aft_negative_min_kNm': '塔底前后向负峰幅值',
    'tower_side_side_absmax_kNm': '塔底侧向绝对极值',
    'tower_top_yaw_absmax_kNm': '塔顶偏航力矩绝对极值',
    'blade1_root_flapwise_positive_max_kNm': '叶1根面外正峰',
    'blade1_root_flapwise_negative_min_kNm': '叶1根面外负峰幅值',
    'rotor_speed_overshoot_vs_12p1_pct': '转速超调',
}
NEG = {'tower_fore_aft_negative_min_kNm', 'blade1_root_flapwise_negative_min_kNm'}

def severity(run, key):
    value = run['metrics'][key]
    return abs(value) if key in NEG else value

def ratio(baseline, perfect, realistic, key):
    b, p, r = (severity(x, key) for x in (baseline, perfect, realistic))
    benefit = b-p
    threshold = 0.01*max(abs(b), 1e-9)  # preregistered here for post-hoc descriptive ratio only
    if benefit <= threshold:
        return {'ratio': None, 'reason': '不适用：完美预视收益非正或不超过基线的1%',
                'baseline': b, 'perfect': p, 'realistic': r,
                'perfect_benefit': benefit, 'realistic_benefit': b-r,
                'near_zero_threshold': threshold}
    return {'ratio': (b-r)/benefit, 'reason': None,
            'baseline': b, 'perfect': p, 'realistic': r,
            'perfect_benefit': benefit, 'realistic_benefit': b-r,
            'near_zero_threshold': threshold}

def show(obj):
    if obj is None:
        return '缺算例'
    return '不适用' if obj['ratio'] is None else f"{obj['ratio']:.3f}"

def main():
    raw = json.loads(SOURCE.read_text())
    assert raw['completed'] == 24 and raw['expected'] == 28
    ix = {(r['case'], r['group']): r for r in raw['runs']}
    assert len(ix) == len(raw['runs'])
    assert set(FIELDS).issubset(raw['runs'][0]['metrics'])
    records = {}
    lines = ['# A3 分段 A：现实/完美预视收益比例补充（仅 v10 有效保护的探索结果）', '',
             '本文件只读后处理 `metrics_A_v10_partial.json`；原 `metrics_A.json` 是保护未开启的 v9 错误探索输出，绝不在其上计算、亦不覆盖。此附表不改变 `RESULTS_A.md` 的未验收状态。', '',
             '定义：同路径、同指标，(反馈极值 − 现实极值)/(反馈极值 − 完美极值)。④以同路径 T=0（超过25 m/s持续50 s关机）为基线，每一请求 T 单独计算。负峰先取幅值；正峰、转速超调按记录原值。分母非正或完美降低量 ≤ 基线幅值的1% 记“不适用”，不强行除；现实变差时可以得到负比例，大于1亦不截断。阈值只是本次比例数值稳定性规则，不是 A/B 的10%试验判据。', '',
             '①–③：', '', '|路径|指标|现实1D比例|现实2D比例|完美收益/基线|', '|---|---|---:|---:|---:|']
    for case in ('I_near', 'III_offset'):
        fb, perf = ix[case, 'feedback'], ix[case, 'perfect']
        records[case] = {'pitch_feedforward': {}, 'shutdown_T': {}}
        for key, label in FIELDS.items():
            a = ratio(fb, perf, ix[case, 'real_1D'], key)
            b = ratio(fb, perf, ix[case, 'real_2D'], key)
            records[case]['pitch_feedforward'][key] = {'real_1D': a, 'real_2D': b}
            baseline = a['baseline']
            frac = a['perfect_benefit']/baseline if baseline else None
            lines.append(f"|{case}|{label}|{show(a)}|{show(b)}|{frac:.2%}|" if frac is not None else f'|{case}|{label}|{show(a)}|{show(b)}|不适用|')
    lines += ['', '④停机 T 扫描：只有现实 1D；未做现实 2D。表中缺算例不补造；T=0 同配置时基线与完美收益为零，比例不适用。', '', '|路径|T 请求(s)|现实实际提前(s)|指标|现实1D/完美收益比例|完美收益/基线|', '|---|---:|---:|---|---:|---:|']
    for case in ('I_near', 'III_offset'):
        fb = ix[case, 'stop_perfect_0']
        for t in (0, 5, 10, 20, 40):
            per = ix.get((case, f'stop_perfect_{t}'))
            real = ix.get((case, f'stop_real_1D_{t}'))
            key_t = str(t)
            records[case]['shutdown_T'][key_t] = {'actual_lead_real_s': real['actual_lead_s'] if real else None,
                                                     'metrics': {}}
            for key, label in FIELDS.items():
                a = ratio(fb, per, real, key) if per is not None and real is not None else None
                records[case]['shutdown_T'][key_t]['metrics'][key] = a
                frac = a['perfect_benefit']/a['baseline'] if a and a['baseline'] else None
                lead = f"{real['actual_lead_s']:.2f}" if real else '缺算例'
                lines.append(f"|{case}|{t}|{lead}|{label}|{show(a)}|{frac:.2%}|" if frac is not None else f'|{case}|{t}|{lead}|{label}|{show(a)}|—|')
    result = {'source': SOURCE.name, 'source_completed': raw['completed'], 'expected': raw['expected'],
              'formula': '(feedback-realistic)/(feedback-perfect); stop: (T0-real_T)/(T0-perfect_T)',
              'negative_extrema': 'absolute magnitudes before comparison',
              'near_zero_policy': 'perfect benefit <= 0.01 * abs(baseline) => null, including nonpositive benefits',
              'limitations': ['v10 old control law, not later requested Guo 2023 law', 'Case III nacelle yaw tracking failed',
                              'deterministic no turbulence', 'Case I four missing runs', 'no 2D stop simulations',
                              'T=0 shutdown uses 50-second sustained-high-wind rule, not instantaneous threshold'],
              'records': records}
    lines += ['', '限制：这是旧版 ROSCO 自写前馈律（θss 差值、固定2 s 滤波/延迟）的历史 v10 探索数，**不是**新要求的 Guo 2023 控制律结果；Case III 实际机舱偏航未跟随；Case I 缺四次；零湍流、无六种子中位数。比例异常大或负数是各指标非单调性或小分母的提示，不作为性能承诺。A2 的 0–17% 仅属另一个建筑 AMD 模型的本线结果，不能直接类推。', '',
              '数据来源：Nguyen (2012) 解析下击暴流场；OpenFAST 5.0.0 NREL 5MW 陆上 + 本地 ROSCO 2.10.6 Apache-2.0 修改版，原始求解在 WSL `segment_a_v10/`/`segment_a_v11/`；本目录 `metrics_A_v10_partial.json` 为后处理输入。']
    for target in (OUT_JSON, OUT_MD):
        if target.exists():
            raise FileExistsError(f'Will not overwrite existing result: {target}')
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    OUT_MD.write_text('\n'.join(lines)+'\n')
    print('created', OUT_JSON, OUT_MD)
    print('pitch entries', sum(len(x['pitch_feedforward']) for x in records.values()), 'stop metric entries', sum(len(t['metrics']) for x in records.values() for t in x['shutdown_T'].values()))

if __name__ == '__main__':
    main()
