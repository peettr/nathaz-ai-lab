"""R4 six-review final: score.json numbers and independent 152-day resampling."""
import csv
import datetime as dt
import hashlib
import json
import pathlib
from collections import defaultdict

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent
SCORE = ROOT / 'r4_score_final_1109/score.json'
MERGED = ROOT / 'r4_score_final_1109/merged_200.jsonl'
EVENTS = ROOT / 'events_r4.csv'
CONTROLS = ROOT / 's0_cpu_v3_1108/pulled_by_lead_1108/controls_r4.csv'
OUTPUT = ROOT / 'r4_score_final_1109/R4_S2_结论定稿_1109.md'
CARD_LOG = pathlib.Path('./23_AI_Weather/06_Logs/convective_r4/EXPERIMENT_CARD_R4.md')
CARD_LINE = pathlib.Path('./23_AI_Weather/11_Subprojects/R23.4/EXPERIMENT_CARD_R4.md')
score = json.loads(SCORE.read_text())
assert score['gates']['verdict'] == '通过' and score['main']['valid_draws'] == 5000
assert score['cohort']['event'] == score['cohort']['control'] == 100
fmt = lambda x: f'{x:.4f}'
def metric(item, key):
    return f"{fmt(item['point'][key])} [{fmt(item['ci'][key]['lower05'])}, {fmt(item['ci'][key]['upper95'])}]"

# Rebuild the post-hoc interval from the 152 *remaining* distinct UTC days.
events = sorted(csv.DictReader(EVENTS.open()), key=lambda r: int(r['order']))
controls = sorted(csv.DictReader(CONTROLS.open()), key=lambda r: int(r['order']))
records = defaultdict(list)
for line in MERGED.open():
    row = json.loads(line)
    if row['status'] == 'ok':
        records[row['unit_index']].append(row)
assert len(events) == len(controls) == 100
by_day = defaultdict(list)
for i, (ev, co) in enumerate(zip(events, controls)):
    for kind, source in [('event', ev), ('control', co)]:
        if kind == 'control' and i in (23, 35, 49):
            continue
        unit = records[2*i + (kind == 'control')]
        base = [r for r in unit if r['kind'] == 'baseline']
        members = [r for r in unit if r['kind'] == 'member']
        assert len(base) == 1 and len(members) == 10
        ai = int(any(float(r['methods']['diagnostic']['wide']['ms']) >= 25.7 for r in members))
        hrrr = int(float(base[0]['fg_wide']['ms']) >= 25.7)
        by_day[source['utc'][:10]].append((kind, ai, hrrr))
days = sorted(by_day)
assert len(days) == 152
rng = np.random.default_rng(20261107)
draws = []
for _ in range(5000):
    sampled = [r for j in rng.choice(len(days), len(days), replace=True)
               for r in by_day[days[j]] if r[0] == 'control']
    assert sampled
    draws.append(sum(a-h for _, a, h in sampled) / len(sampled))
lo, hi = map(float, np.percentile(draws, [5, 95]))
assert abs(lo - (-0.05434782608695652)) < 1e-12
assert abs(hi - 0.07446808510638298) < 1e-12
post = score['without_orders_23_35_49_false_alarm']
assert post['cohort']['control'] == 97
assert abs(post['point']['false_diff'] - 1/97) < 1e-12
p = score['main']['point']
ci = score['main']['ci']
top = score['topk']
dev = score['without_developer_period']
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert CARD_LOG.exists() and CARD_LINE.exists()
assert CARD_LOG.read_bytes() == CARD_LINE.read_bytes()
assert '⑤ 结果与结论回填' in CARD_LOG.read_text()
now = dt.datetime.now(dt.timezone(dt.timedelta(hours=-5))).strftime('%Y-%m-%d %H:%M EST')
lines = [
    '# R4-S2 结论定稿（六审裁决 0aeddcd6）',
    '',
    f'生成：{now}。数值源：`r4_score_final_1109/score.json`（SHA-256 {sha(SCORE)}）；冻结评分脚本 `r4_score_v4.py`（SHA-256 {sha(ROOT / "r4_score_v4.py")}）；积分合并输入 `merged_200.jsonl`（SHA-256 {sha(MERGED)}）。以下所有主评分数值从 score.json 读取，唯一新增删后三对照区间从原始合并记录重抽。',
    '',
    f'实验卡⑤结果与结论已回填并同步（两处文件 SHA-256 均为 {sha(CARD_LOG)}）：`{CARD_LOG}`；`{CARD_LINE}`。',
    '',
    '## 冻结配置与判据',
    f'有效事件/对照 {score["cohort"]["event"]}/{score["cohort"]["control"]}；剔除 {score["cohort"]["attempted_exclusions"]}，重跑 {len(score["cohort"]["rerun_units"])}；有效 UTC 日簇 bootstrap {score["main"]["valid_draws"]} 次，种子 20261107，区间为第 5/95 百分位。StormCast V1，Benjamin 2020 方法 a，HRRR 分析起报与 ERA5 后验条件场，10 成员（种子 101–110）；看过 S2 后选的“任一成员”阈值聚合、十成员最大峰值；HRRR fg10m 对照。',
    '事件与对照各单元在站点 25 km、起报后积分 1–3 h（2 h 主时效，±1 h 宽窗）内取最大诊断阵风/HRRR fg10m；阈值 25.7 m/s。命中/误报是事件/对照上任一有效成员达到阈值的二值判定。',
    'H=事件命中数/有效事件数，F=对照误报数/有效对照数；ΔH=H_AI−H_HRRR，ΔF=F_AI−F_HRRR。对事件 i，ρ_i=max_m(成员 m 的宽窗最大诊断阵风)/HRRR 宽窗最大 fg10m；汇报 median_i ρ_i。',
    'BS(P)=N⁻¹Σ_i(P_i−y_i)²；BS 差=BS_AI−BS_HRRR，其中 P_i 是达到阈值的有效成员比例，HRRR 取二值 0/1；任一成员二值 BS 则把 AI 的 P_i 换为任一成员命中指示。Peirce 技巧分=H−F；Peirce 差=(H_AI−F_AI)−(H_HRRR−F_HRRR)。s2_original 只报告口径为 P≥0.3 的命中/误报和成员中位峰值/HRRR 峰值，不能替代主判据。',
    '',
    '## 主判据与两读法',
    f'命中 H_AI={fmt(p["hit_ai"])}（{round(p["hit_ai"]*100)}/100），H_HRRR={fmt(p["hit_hrrr"])}（{round(p["hit_hrrr"]*100)}/100），ΔH={metric(score["main"], "hit_diff")}；下界 >−0.15 且点估计 ≥−0.05：{score["gates"]["hit"]}。双方命中都低。',
    f'误报 F_AI={fmt(p["false_ai"])}（{round(p["false_ai"]*100)}/100），F_HRRR={fmt(p["false_hrrr"])}（{round(p["false_hrrr"]*100)}/100），ΔF={metric(score["main"], "false_diff")}；上界 <+0.15 且点估计 ≤+0.05：{score["gates"]["false_numerical"]}；仅“未触发 §2.3 无区分力定义”，区间含零，不能声称已证明有区分力。少数单元改变即可影响误报差。',
    f'事件 median ρ={metric(score["main"], "peak_ratio_event")}；点估计 ≥1 且下界 ≥0.9：{score["gates"]["peak"]}。对照 median ρ={fmt(p["peak_ratio_control"])}（约 1.151，仅报告）；峰值偏高不受主判据上界约束。',
    '按预注册 §2.3 专门定义探索性的条款与 Lead 裁定：偏离未影响主判据，故非探索性、冻结四分支判定“通过”。理由：排除日补定早于对照/worker/评分冻结且早于 AI 积分，另列只报告敏感性；S2b 跳过获 §6 允许；R4-D1 的 v3 已在冻结清单。另一读法若把预注册第 5 行理解为“任何偏离记录都自动探索性”，则同一结果总判定须写“探索性”，而非通过；两读法并列披露，不改任何评分数值。',
    '',
    '## 只报告、事后、不改判据',
    f'P 的 BS 差 {metric(score["main"], "bs_p_diff")}；任一成员二值 BS 差 {metric(score["main"], "bs_binary_diff")}；Peirce 差 {metric(score["main"], "peirce_diff")}。',
]
for key, label in [('s2_original', 'S2 原口径'), ('factor16777', '1.6677 系数'),
                   ('hrrrcast_without_vvel', 'HRRRCast 无 VVEL'), ('narrow', '窄窗'),
                   ('same_formula_hrrr', 'HRRR 同公式副对照')]:
    item = score['report_only'][key]
    lines.append(f'{label}：事件/对照 {item["cohort"]["event"]}/{item["cohort"]["control"]}，ΔH {metric(item,"hit_diff")}，ΔF {metric(item,"false_diff")}，事件 median ρ {metric(item,"peak_ratio_event")}；有效抽样 {item["valid_draws"]}。')
near = score['near_threshold_only_false_alarm']
lines += [
    f'仅近阈对照：本轮补位 0，故此项与主结果恒等：ΔF {metric(near,"false_diff")}。',
    f'去开发者评价期（剔除 2022 与 2024-05-08—06-15）：事件/对照 64/64，ΔH {metric(dev,"hit_diff")}，ΔF {metric(dev,"false_diff")}，事件 median ρ {metric(dev,"peak_ratio_event")}；这是最贴近界限的敏感性，有效抽样 {dev["valid_draws"]}。',
    f'去对照 order 23/35/49：原 score.json 沿主样本 153 日抽样序列，删后 2024-06-28 是空日，ΔF {metric(post,"false_diff")}；按删后有效 152 日重新用同种子/同法抽样 5000 次，ΔF 点估计 {fmt(post["point"]["false_diff"])}、区间 [{fmt(lo)}, {fmt(hi)}]，与审稿人 E [−0.0543, +0.0745] 一致。此敏感性仅 97 个对照，F_AI={fmt(post["point"]["false_ai"])}，F_HRRR={fmt(post["point"]["false_hrrr"])}，误报肢仍满足；不改主判据。',
    '',
    '## 排序、覆盖与限制',
    'Top-k 在全部有效事件+对照按峰值降序、并列按 order 升序；捕获率=前 k 事件数/100，精度=前 k 事件数/k。AI 在 k=10/25/50/100 四档捕获率与精度均低于 HRRR：',
    '| k | AI 捕获率 | HRRR 捕获率 | AI 精度 | HRRR 精度 |',
    '|---:|---:|---:|---:|---:|',
]
for k in ('10','25','50','100'):
    a, h = top['ai'][k], top['hrrr'][k]
    assert a['capture'] < h['capture'] and a['precision'] < h['precision']
    lines.append(f'| {k} | {fmt(a["capture"])} | {fmt(h["capture"])} | {fmt(a["precision"])} | {fmt(h["precision"])} |')
coverage = score['coverage_thunderstorm']
mc = score['mcnemar']
lines += [
    f'观测落在成员峰值最小—最大范围的覆盖率：事件 {coverage["event"]["covered"]}/{coverage["event"]["n"]}={fmt(coverage["event"]["fraction"])}；对照 {coverage["control"]["covered"]}/{coverage["control"]["n"]}={fmt(coverage["control"]["fraction"])}（不是名义置信区间）。',
    f'McNemar 事件不一致对 AI-only={mc["discord_ai_only"]}、HRRR-only={mc["discord_hrrr_only"]}，精确双侧 p={fmt(mc["p_exact_two_sided"])}；“优于 HRRR”送审条件={score["better_than_hrrr_eligible_for_review"]}，不作优劣归因。',
    '偏离：§2.2③ 排除日由 Lead 事后补定为 ASOS hit.utc 的 UTC 日，另一读法去 23/35/49 如上；§6 S2b 因冻结 worker 分段断言不支持 20 个事件而按协议跳过；R4-D1 的 S0 v3 实际仅给 IEM asos.py ≥2.05 s 串行限速，雷达 WMS 仍 10 线程，429 退避 30·2^i s、不读 Retry-After；失败记 unretrieved 继续，最终非空则退出码 3、拒绝冻结。其文字更正已另追加 DEVIATIONS.md；本轮 S0 unretrieved=0，100 近阈对照、补位 0、缺对照 0。35 dBZ 敏感性本轮不做，对照不另配。',
    'S2b 未做，故 ERA5 预报时段后验条件场更新带来的有利幅度未量化；整个 ERA5 本身亦非业务起报时可得。本轮复合变化（聚合、盲样本、近阈对照）不能单独归因于聚合，不能外推实时业务预报。',
    '',
    '## 给 Liang Hu 的结论',
    f'R4 冻结判据{score["gates"]["verdict"]}——限 StormCast V1＋Benjamin 2020 方法 a＋看过 S2 后选的“任一成员”口径、本清点母体、回报配置（预报时段 ERA5 后验条件场）；不表示命中不差于 HRRR：双方命中率都低（19% 对 20%），Top-k 四档 AI 均低于 HRRR，事件覆盖率 10%。按 §2.3 专门条款裁定非探索性；若将预注册第 5 行读成任何偏离即探索性，则总判定为“探索性”。通过不表示峰值准确、不恢复 S2 已否定的 P 用法，也不等于值得上规模。',
]
assert not OUTPUT.exists(), f'new output already exists: {OUTPUT}'
OUTPUT.write_text('\n'.join(lines)+'\n')
print(json.dumps({'output':str(OUTPUT),'rebootstrap_days':len(days),'ci':[lo,hi],
                  'score_verdict':score['gates']['verdict']},ensure_ascii=False))
