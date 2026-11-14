"""Render the frozen R4 score JSON as a bounded draft, without manual score entry."""
import datetime as dt
import hashlib
import json
import pathlib

root = pathlib.Path(__file__).resolve().parent
score_path = root / 'r4_score_final_1109/score.json'
score = json.loads(score_path.read_text())
assert score['cohort']['event'] == score['cohort']['control'] == 100
assert score['cohort']['attempted_exclusions'] == 0 and score['invalid_json_lines'] == 0
p, ci = score['main']['point'], score['main']['ci']
assert score['main']['valid_draws'] >= 4900
fmt = lambda x: f'{x:.4f}'
metric = lambda name: f"{fmt(p[name])} [{fmt(ci[name]['lower05'])}, {fmt(ci[name]['upper95'])}]"
lines = [
    '# R4-S2 结论草案（程序由冻结评分表生成，待 Lead 核审）',
    '',
    f"生成：{dt.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')}。评分脚本 r4_score_v4.py SHA-256 {hashlib.sha256((root/'r4_score_v4.py').read_bytes()).hexdigest()}；合并脚本 r4_merge_final_1109.py SHA-256 {hashlib.sha256((root/'r4_merge_final_1109.py').read_bytes()).hexdigest()}。",
    f"输入：r4_score_final_1109/merged_200.jsonl（SHA-256 {hashlib.sha256((root/'r4_score_final_1109/merged_200.jsonl').read_bytes()).hexdigest()}），输出：r4_score_final_1109/score.json；种子/簇抽样按冻结脚本 §3。",
    '',
    '样本：冻结的 StormCast V1 + 方法 a、100 事件＋100 近阈对照回报配置；每单元 1 条 HRRR 基线＋10 个有效成员，种子 101–110。剔除 0、重跑 0；5000 次有效 UTC 日簇 bootstrap。差值均为 AI−HRRR，区间均为 5–95 百分位。',
    '定义：H=事件命中数/有效事件数，F=对照误报数/有效对照数；ΔH=H_AI−H_HRRR，ΔF=F_AI−F_HRRR；ρ_i=max_m(成员 m 的宽窗最大诊断阵风)/HRRR 宽窗最大 fg10m；主时效 2 h，阈值 25.7 m/s。',
    f"命中：AI {fmt(p['hit_ai'])}，HRRR {fmt(p['hit_hrrr'])}，ΔH={metric('hit_diff')}；下界 >−0.15 且点估计 ≥−0.05：{score['gates']['hit']}。",
    f"误报：AI {fmt(p['false_ai'])}，HRRR {fmt(p['false_hrrr'])}，ΔF={metric('false_diff')}；上界 <+0.15 且点估计 ≤+0.05：{score['gates']['false_numerical']}；无区分力：{score['gates']['false_uninformative']}。",
    f"事件峰值比：median ρ={metric('peak_ratio_event')}；点估计 ≥1.0 且下界 ≥0.9：{score['gates']['peak']}。对照 median ρ={fmt(p['peak_ratio_control'])}，只报告。",
    f"四分支总判定（按预注册 §2.3 顺序）：{score['gates']['verdict']}；探索性标记：{score['gates']['exploratory']}。这里的“通过”不表示 AI 命中不差于 HRRR（n=100 时真实差 −5 个百分点仍有约一半概率判通过）；不表示峰值准确或不偏高；不恢复 S2 已否定的概率（P）用法；不等于“值得上规模”的业务结论；只限本配置、本清点母体、回报。ERA5 在预报时段内的后验条件场使本配置不能外推为业务实时预报。",
    '', '只报告（不可替代主判定）：',
    f"P 的 BS 差 {fmt(p['bs_p_diff'])}；任一成员二值 BS 差 {fmt(p['bs_binary_diff'])}；Peirce 技巧分差 {fmt(p['peirce_diff'])}。",
]
for key, item in score['report_only'].items():
    q = item['point']; c = item['ci']
    lines.append(f"{key}：事件/对照={item['cohort']['event']}/{item['cohort']['control']}，有效抽样={item['valid_draws']}，ΔH={fmt(q['hit_diff'])} [{fmt(c['hit_diff']['lower05'])}, {fmt(c['hit_diff']['upper95'])}]，ΔF={fmt(q['false_diff'])} [{fmt(c['false_diff']['lower05'])}, {fmt(c['false_diff']['upper95'])}]，事件峰值比={fmt(q['peak_ratio_event'])} [{fmt(c['peak_ratio_event']['lower05'])}, {fmt(c['peak_ratio_event']['upper95'])}]。")
for name, item in [('仅近阈对照',score['near_threshold_only_false_alarm']), ('去开发者评价期',score['without_developer_period'])]:
    q, c = item['point'], item['ci']
    lines.append(f"{name}：ΔF={fmt(q['false_diff'])} [{fmt(c['false_diff']['lower05'])}, {fmt(c['false_diff']['upper95'])}]。")
q = score['without_orders_23_35_49_false_alarm']
lines.append(f"事后歧义敏感性（只报告，去对照 order 23/35/49）：对照数 {q['cohort']['control']}，ΔF={fmt(q['point']['false_diff'])} [{fmt(q['ci']['false_diff']['lower05'])}, {fmt(q['ci']['false_diff']['upper95'])}]，不改主判据。")
lines.append('Top-k 定义：全部有效事件+对照按峰值降序、并列按 order 升序；捕获率=前 k 事件数/有效事件总数，精度=前 k 事件数/k。')
for name, table in score['topk'].items():
    lines.append(name + '：' + '；'.join(f"k={k} 捕获 {v['event_count']}/100={fmt(v['capture'])}、精度={fmt(v['precision'])}" for k,v in table.items()))
lines.append('覆盖率定义：观测阵风处于成员宽窗峰值最小—最大之间的单元比例；按灾种雷暴的事件/对照分别报，非名义置信区间。')
for name, x in score['coverage_thunderstorm'].items():
    lines.append(f"雷暴 {name}：{x['covered']}/{x['n']}={fmt(x['fraction'])}。")
m = score['mcnemar']
lines.append(f"McNemar 不一致对 AI-only={m['discord_ai_only']}、HRRR-only={m['discord_hrrr_only']}，精确双侧 p={fmt(m['p_exact_two_sided'])}；提出优于 HRRR 的送审条件={score['better_than_hrrr_eligible_for_review']}，不作优劣归因。")
lines += ['', '偏离/限制：§2.2③ 排除日按 Lead 事后补定，order 23/35/49 另作上面只报告敏感性；S2b 冻结 worker 不支持 20 事件抽样，按 §6 实现不了则跳过，不修改冻结文件（详见 DEVIATIONS.md）。35 dBZ 敏感性本轮按预注册不做。', '本结论是看过 S2 后挑选聚合口径在新盲样本上的回报检验，不单独归因于聚合改变；科学判定须由 Lead 核审。']
out = root / 'r4_score_final_1109/R4_S2_结论草案_1109.md'
with out.open('x') as f:f.write('\n'.join(lines)+'\n')
print(out)
