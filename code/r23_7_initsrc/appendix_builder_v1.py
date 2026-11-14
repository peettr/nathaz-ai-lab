#!/usr/bin/env python3
"""Render post-review disclosure from archived metrics and independently calculated audits."""
import json
from pathlib import Path
R=Path(__file__).resolve().parent;D=R/'m2_2023_v1/assembled_v1'
arch=json.loads((D/'metrics_v1.json').read_text());chain=json.loads((D/'sample_chain_v1.json').read_text());desc=json.loads((D/'descriptive_v2.json').read_text())
main=arch['main'];raw=arch['raw_main'];cells=arch['all_cells']
def f(x,n=5):return 'NA' if x is None else f'{x:.{n}f}'
def st(year,name):return next(x for x in chain[year] if x['stage']==name)
def b(x):return x['by_lead']
tr0=st('training','paired_nonmissing_METAR');tr=st('training','six_arm_common');te0=st('test','paired_nonmissing_METAR');sre=st('test','R23_2a_SRE_summer_removed');pre=st('test','primary_init_at_or_after_2023_01_18');five=st('test','five_arm_full_year_after_SRE_and_METAR');six=st('test','six_arm_common')
assert tr['unique_station_init_lead_keys']==8024 and b(six)['24']==main['paired_keys'] and b(five)['24']==arch['counts']['test_five_observed_keys']
miss={r['source']:r for r in chain['test'] if r['stage']=='source_missing_from_preintersection'}
assert sum(r['missing_keys'] for r in miss.values())==pre['unique_station_init_lead_keys']-six['unique_station_init_lead_keys']
assert arch['overall_verdict']=='分不出'
source='./31_Core_Lab/05_Projects/L31.9_工作/L31.9c/评价判据规矩_极端事件评价协议_20261024.md'
L=['# R23.7 结果附注 v1（六审披露，不修改冻结评分）','',f'冻结主判定仍为「{arch["overall_verdict"]}」：24 h 六臂共同样本、2022 订正、δ=0.02，C={f(main["C"],8)}，95% 区间 [{f(main["C_ci95"][0],8)}, {f(main["C_ci95"][1],8)}]。仅限本配置。原 results_v1.md、metrics_v1.json 和 score_v1.py 均保持不变。','',
'## 定义、区间与主口径','',
'MAE(m,s) = Σ|预测风速−METAR 风速| / n；d_m = [MAE(m,GFS初值)−MAE(m,IFS初值)]/MAE(m,IFS初值)，m=GC 或 PG；C=d_GC−d_PG。仅供对照的 d_phys=[MAE(GFS物理臂)−MAE(HRES)]/MAE(HRES)，以及 d_GC−d_phys、d_PG−d_phys，不参与判定。',
'95% 区间按 UTC 验证日整组、配对重抽样；六臂共用每次同一组验证日权重，重抽 1000 次，种子 20261108，取 2.5%/97.5% 百分位（score_v1.py 第 89–110 行）。主样本每个臂均取同一站点、起报、时效和观测；24 h 主、48 h 次。','',
'## 从原站点序列逐项生成的剔除链','',
'下列均为唯一（站点、起报 UTC、时效）键，非六臂行数；2022 的训练共同键合计 24 h 与 48 h，2023 检验格单独计 24 h。数字由 sample_chain_v1.py 从站点序列重新计算、并与冻结 metrics_v1.json 断言核对。',
'|步骤|2022 训练 24/48|2023 检验 24/48|本步剔除（合计）|','|---|---:|---:|---:|',
f'|R23.2a GFS 旧表、有 METAR|{b(tr0)["24"]}/{b(tr0)["48"]}|{b(te0)["24"]}/{b(te0)["48"]}|训练 0、检验 0（均已配对）|',
f'|2023 6–9 月 SRE 排除|—|{b(sre)["24"]}/{b(sre)["48"]}|{te0["unique_station_init_lead_keys"]-sre["unique_station_init_lead_keys"]}|',
f'|2023-01-18 起报（主样本窗口）|—|{b(pre)["24"]}/{b(pre)["48"]}|{sre["unique_station_init_lead_keys"]-pre["unique_station_init_lead_keys"]}|',
f'|2022 六臂共同 / 2023 六臂共同|{b(tr)["24"]}/{b(tr)["48"]}|{b(six)["24"]}/{b(six)["48"]}|训练 {tr0["unique_station_init_lead_keys"]-tr["unique_station_init_lead_keys"]}、检验 {pre["unique_station_init_lead_keys"]-six["unique_station_init_lead_keys"]}|',
f'|2023 全年五臂（无 HRES）|—|{b(five)["24"]}/{b(five)["48"]}|相对 SRE 后 {sre["unique_station_init_lead_keys"]-five["unique_station_init_lead_keys"]}|','',
'2023 原表有其他提前量：上述起点只计 24/48 h。SRE 6–9 月筛选继承 R23.2a 修正版 run_verify_v2.py 第 112–115 行；旧 run_verify_revised.py 不含此筛选，预注册复现目标 7917 已隐含它，不是事后新设判据。2022 PG·IFS 的 2022-12-01 00 UTC 缺档导致全部臂一起少 20 个站点×时效键（24 h 10、48 h 10），共用键为 8024（4016+4008），并非单一时效。',
f'2023 主窗口源缺键：PG·IFS {miss["PANG_v100_IFS"]["missing_keys"]}（24/48 各 {b(miss["PANG_v100_IFS"])["24"]}/{b(miss["PANG_v100_IFS"])["48"]}），HRES {miss["HRES"]["missing_keys"]}（{b(miss["HRES"])["24"]}/{b(miss["HRES"])["48"]}），两者合计剔除 {pre["unique_station_init_lead_keys"]-six["unique_station_init_lead_keys"]} 键；其余源此窗口缺键数为 0。此为已与旧 GFS 配对的站点键的覆盖差，不等于原始归档缺失的对象数。全年五臂相对 SRE 后少 {sre["unique_station_init_lead_keys"]-five["unique_station_init_lead_keys"]} 键。详细阶段数与来源分解见 sample_chain_v1.json。','',
'## HRES 口径与订正敏感性','',
'2022 HRES 来自 WB2 0.25°，2023 来自 Open Data 0.4°；2022 拟合的订正系数直接用于 2023，因此 d_phys、GC−phys 和 PG−phys 不是相同分辨率口径的物理基线，只作参考；不能将之解释为初值系统的一般优劣或约 2% 的跨系统优势。不含 HRES 的全年五臂 24 h 订正 δ=0.02 同样「分不出」。',
f'24 h 主格：订正后 C={f(main["C"],6)}「{main["verdict"]}」，未订正 C={f(raw["C"],6)}「{raw["verdict"]}」，未订正 d_PG={f(raw["d_PG"],6)} 为负（本样本的 PG·GFS 未订正 MAE 小于 PG·IFS）。',]
cor48=next(c for c in cells if c['cohort']=='primary' and c['lead_h']==48 and c['variant']=='corrected' and c['delta']==.02)
raw48=next(c for c in cells if c['cohort']=='primary' and c['lead_h']==48 and c['variant']=='raw_speed' and c['delta']==.02)
L += [f'48 h、δ=0.02：订正后 C={f(cor48["C"],6)}「{cor48["verdict"]}」，未订正 C={f(raw48["C"],6)}「{raw48["verdict"]}」；这是次要格的支持/不支持相反两向，必须披露，但不改 24 h 总判定。方案的「不同向」较宽，冻结预注册收窄为「一个支持、一个不支持」；主格订正后分不出/未订正支持不触发后者。两种读法下总判定都不会是「支持」；「不触发冲突规则」绝非「订正不影响结论」。','',
'## 附加描述性补算（不进判定）','',
'Brier = Σ(p−1{观测风速≥8})²/n；BSS=1−Brier/[Σ(q−y)²/n]。q22 是对应时效、2022 六臂训练共同样本的观测事件率（仅从 2022 拟合）；q23 是同一 2023 检验共同样本的事件率，只作为事后样本参照，不用于拟合预测或阈值。原 score_v1.py 用的是 q23，不是 R23.2a 的训练年参照口径。',
'Top-k（k=1%、5%、10%）选择数 ceil(k·n)，捕获率 = 被选中的观测 ≥8 m/s 事件数 / 全部观测 ≥8 m/s 事件数；按预测概率降序、站点升序、起报时刻升序稳定排序（R23.2a run_verify_v2.py 第 223–239 行）。原 score_v1.py 的同概率次序为起报优先于站点；以下并列审计显示所有 18 个臂×k 截点都没有跨界并列，故逐格捕获数差均为 0。',
'阈值 8 与 10 m/s 取自 R23.2a run_verify_v2.py 第 240–258 行；作为事后描述口径，不是假装在 R23.7 预注册中预先确定的 twMSE 判定阈值。twMSE=mean[(y−t)₊²−(x−t)₊²−2(y−x)(x−t)₊]，x 为用 2022 系数订正的确定性风速，y 为 METAR 2-min 风速。H=观测和预报均≥t，M=观测≥t但预报<t，F=观测<t但预报≥t，TN=均<t；MR=M/(H+M)，FAR=F/(H+F)，FB=(H+F)/(H+M)。owMSE 仅在观测≥t 上计算、不罚误报，不用于排名；twMSE 与 MSE 分母是全部 n。按 L31.9c 评价判据规矩 v1 第 2–3 条报告，见下方逐臂两阈值计数和得分。',
'规矩路径：'+source+'（第 55–97 行；来源文献卡 16_PETW/05_Literature_Wiki/wiki/ai_weather/papers/NR_biegert_2026_evaluation_protocols.md，PDF pp.4–5、8、14–15）。这仅是补充诊断，不做 twMSE 模型排名，也未估计基于事件/季的区间或样本内 PAV 校准分解；不把这份事后补算当作预注册极端评价协议的完整执行。','']
for cohort,leads in desc['cohorts'].items():
    for lead,cell in leads.items():
        L += [f'### {cohort}，{lead} h',f'全部配对 n={cell["n"]}；观测 ≥8 m/s 事件 {cell["events_8mps"]}；2022 训练事件 {cell["climatology_2022"]["events"]}/{cell["climatology_2022"]["n"]}（q22={f(cell["climatology_2022"]["event_rate"],6)}），2023 样本 q23={f(cell["sample_2023"]["event_rate"],6)}。以下每一臂的分母均为本段 n；每个阈值的事件、预报事件数另由 H/M/F 给出。','',
'|臂|BSS/q22|BSS/q23|','|---|---:|---:|']
        for source,a in cell['arms'].items():L.append(f'|{source}|{f(a["BSS_vs_2022_climatology"],6)}|{f(a["BSS_vs_2023_sample_rate"],6)}|')
        L += ['','|臂|阈值 m/s|twMSE|MSE|H|M|F|TN|MR|FAR|FB|twMSE 贡献 H/M/F (%)|','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
        for source,a in cell['arms'].items():
            for t,z in a['thresholds'].items():
                shares=z['twMSE_share_by_category']; sh='/'.join(f(shares[k]*100,1) for k in ('hit','miss','false_alarm'))
                L.append(f'|{source}|{t}|{f(z["twMSE"],5)}|{f(z["unconditional_MSE"],5)}|{z["H"]}|{z["M"]}|{z["F"]}|{z["correct_negative"]}|{f(z["MR"],4)}|{f(z["FAR"],4)}|{f(z["FB"],4)}|{sh}|')
        L += ['','注：贡献为各类 twMSE 和除以全体 twMSE 和，误报类的式项可有符号；不把份额解释为经济损失权重。各臂均用同一组站点键。','']
L += ['### 主格 Top-k 并列审计（2023 六臂 24 h）','','|臂|前 1% 捕获|前 5% 捕获|前 10% 捕获|各截点跨界并列|与冻结版命中数差|','|---|---:|---:|---:|---|---|']
for source,a in desc['cohorts']['primary_six_2023_01_18']['24']['arms'].items():
    top=a['top_k'];tie=['%s:%s/%s'%(k,z['boundary_selected_rows'],z['boundary_tied_rows']) for k,z in top.items() if z['boundary_tied_rows']>1]
    L.append(f'|{source}|'+ '|'.join(f(top[k]['R23_2a_capture'],6) for k in ('0.01','0.05','0.1'))+f'|{", ".join(tie) if tie else "无"}|'+','.join(str(top[k]['difference_hits']) for k in ('0.01','0.05','0.1'))+'|')
L += ['','截点处各只有一条同概率记录（其本身当然等于截点概率），故没有需打破的跨界并列；详细选择数、概率、并列事件数见 descriptive_v2.json。','',
'## 冻结证据等级与证据路径','',
'冻结时序仅由本机文件修改时间、机器 date 与 sha256 支持，没有外部可信时间戳；实验卡标题「M2/M3 冻结」下面同时记录了 14:19 以后发生的取数和运行事件，它们不是 14:14 的冻结证据。',
'归档：本目录 results_v1.md、metrics_v1.json；核对脚本在 R23.7 根目录 sample_chain_v1.py、descriptive_v2.py；数值附表为本目录 sample_chain_v1.json、descriptive_v2.json。无覆盖原始结果。','']
p=D/'results_v1_附注.md';assert not p.exists();p.write_text('\n'.join(L))
print(json.dumps({'path':str(p),'line_count':len(L),'main_C':main['C'],'chain_test_24':b(six)['24'],'description_cohorts':list(desc['cohorts'])},ensure_ascii=False))
