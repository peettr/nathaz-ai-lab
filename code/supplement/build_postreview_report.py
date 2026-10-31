#!/usr/bin/env python3
"""Format M6 frozen tables and postreview tables, no hand-copied metric values."""
from pathlib import Path
import json, hashlib
import pandas as pd
R=Path(__file__).resolve().parents[1]; S=R/'supplement'; F=R/'output_final'
assert json.loads((S/'parity.json').read_text())['passed']
main=pd.read_csv(F/'main.csv'); main=main[main.delay_h==4].set_index(['lead_min','metric'])
auc0=pd.read_csv(F/'secondary_auc_delay4.csv'); auc=pd.read_csv(S/'auc_site_ci.csv'); top=pd.read_csv(S/'topk_corrected.csv'); rel=pd.read_csv(S/'B_D2_vs_P.csv').set_index('lead_min'); groups=pd.read_csv(S/'groups.csv'); tau=pd.read_csv(S/'tau.csv'); coverage=pd.read_csv(F/'coverage_delay4.csv'); sites=pd.read_csv(S/'site_mae.csv')
leads=[10,20,30,60,120,180,240,300,360];methods=['P','R','F','F_D','B','B_D','T0','D2','B_R','B_T0','B_D2'];edges=['R_to_F','F_to_F_D','F_to_B','F_D_to_B_D','B_to_B_D','R_to_T0','R_to_D2','T0_to_D2','B_R_to_B_D2','B_T0_to_B_D2']
assert len(auc)==len(leads)*(len(methods)+len(edges)) and len(top)==len(leads)*(len(methods)+len(edges))*3*2
assert len(groups)==len(leads)*6 and len(tau)==180 and len(sites)==len(leads)*12
fmt=lambda v:f'{v:.3f}'; pct=lambda v:f'{100*v:.2f}%';ci=lambda r:f"{fmt(r['point'])} [{fmt(r['lo'])}, {fmt(r['hi'])}]"
base=(R/'results.md').read_text().split('\n## 六审 65f0f7e0 后的限定结论')[0]
base=base.replace('# R23.2-04 M6 整链分段增量首试 · 结果（10-28 20:52 EDT）','# R23.2-04 M6 整链分段增量首试 · 结果（10-28 20:52 冻结；六审 65f0f7e0 后修订 10-29 01:2x EDT）')
base=base.rstrip()+'\n'
base=base.replace('两个主判均通过：每个提前量的上界均小于 0，预注册止损未触发。此为本配置、本样本的平均风速 MAE 判据，不代表强风预警或单站可靠性。','两条主判九档上界均小于 0，按冻结预注册通过、止损未触发；这些日块区间未量化多日天气相关性，逐档稳健性不能由此保证。主判仅针对本配置、本样本的合并平均风速 MAE。')
small=main.loc[(10,'D_A'),'point'];long=main.loc[(360,'D_A'),'point'];small_b=main.loc[(10,'D_B'),'point'];long_b=main.loc[(360,'D_B'),'point'];lo_p,hi_p=rel.B_D2_vs_P.min(),rel.B_D2_vs_P.max()
intro=f'''\n## 六审 65f0f7e0 后的限定结论\n\n在 GFS 0.25°、发布延迟 4 h（假设）、瑞士冻结 12 站、2024 年 1–3 月检验的配置下，两条冻结主判九个提前量的日块 95% 上界都小于零，按预注册通过，止损未触发。\n\n有本站历史时，B_D 相对 B 的 MAE 差 D_A=(MAE_B_D−MAE_B)/MAE_B：10 min {pct(small)}，360 min {pct(long)}；10 min 绝对改善 {fmt(main.loc[(10,'MAE_B'),'point']-main.loc[(10,'MAE_B_D'),'point'])} m/s，30 min {fmt(main.loc[(30,'MAE_B'),'point']-main.loc[(30,'MAE_B_D'),'point'])} m/s。增量按构造只来自 Δz>0 的七站，主要见 CHA、DOL、CDM、NAP；Δz≤0 五站 V1=R，B_D=B（浮点精度内）。\n\n无本站历史时，B_D2 相对两条预注册融合对照的较好者 D_B 从 {pct(small_b)} 到 {pct(long_b)}，九档较好者全为 B_R；但 B_R 从 30 min 起 MAE 高于纯持续性 P（360 min {fmt(main.loc[(360,'MAE_B_R'),'point'])} 对 {fmt(main.loc[(360,'MAE_P'),'point'])} m/s），不能把 D_B 解释成相对 P 的改善。事后 10-28 的 B_D2 相对 P 的差值及区间见下表，点值范围 {pct(lo_p)} 至 {pct(hi_p)}；360 min 有 {sum((sites[sites.lead_min==360].MAE_B_D2>sites[sites.lead_min==360][['MAE_B_R','MAE_B_T0']].min(axis=1)))} 站差于其较好融合基线。\n\n结论只针对 10 分钟平均风速合并 MAE，不涉及强风预警或单站区间可靠性。以下均为“事后 10-28”修正/补充，不参加冻结主判；原判据的读法仍是上述 D_A、D_B。\n'''
sec=['## 副指标：事后 10-28（不改主判）','','站内 AUC 为每站先算 AUC 后十二站等权平均；合并 AUC 把跨站绝对风速排序，可能与站内方向相反。以下各表的区间均为 UTC 检验日整块有放回抽样 1000 次、2.5%/97.5% 分位；站内 AUC 采用同一副本两方法配对作差。','',
'|L min|AUC 站内 B→B_D (两点值；差值 95% 区间)|AUC 站内 B_R→B_D2 (两点值；差值区间)|AUC 合并 B→B_D|AUC 合并 B_R→B_D2|','|---:|---|---|---|---|']
for L in leads:
 def aa(m,metric):return float(auc[(auc.lead_min==L)&(auc.method==m)&(auc.metric==metric)].iloc[0].point)
 def diff(a,b):return auc[(auc.lead_min==L)&(auc.method==f'{a}_to_{b}')].iloc[0]
 def pooled(m):return float(auc0[(auc0.lead_min==L)&(auc0.method==m)&(auc0.metric=='AUC_pooled')].iloc[0].point)
 sec.append(f'|{L}|{fmt(aa("B","AUC_site_mean"))}→{fmt(aa("B_D","AUC_site_mean"))} ({ci(diff("B","B_D"))})|{fmt(aa("B_R","AUC_site_mean"))}→{fmt(aa("B_D2","AUC_site_mean"))} ({ci(diff("B_R","B_D2"))})|{fmt(pooled("B"))}→{fmt(pooled("B_D"))}|{fmt(pooled("B_R"))}→{fmt(pooled("B_D2"))}|')
sec+=['','AUC 全部 11 方法点值与十条边站内差的完整区间见 supplement/auc_site_ci.csv；合并 AUC 十条边的冻结差值区间仍见 output_final/secondary_auc_delay4.csv。不能概括成“强风预警改善”，合并下降也不代表站内识别变差。','','### Top-k：按条 / 按事件','',
'同一 L 各方法全部检验行排序（pooled）和每站分别排序（within_site）并列；每个评分行对应的强风事件来自原生十分钟观测。点值按原事件号；重抽时以（抽中的日块副本序号，原事件号）为独立事件号，跨日事件在重抽副本按日切开。分母是有评分行的事件，不是全部原生观测事件。原 output_final/topk_delay4.csv 的 events_lo/hi 及事件差区间因重抽重复日合并事件而作废，不得引用；其点值和按条指标不受影响。订正全表为 supplement/topk_corrected.csv，含六种 k/排序口径下全部 11 方法和十条配对边的点值与区间。','',
'|L min|排序|k|B 按条/事件|B_D 按条/事件|B_R 按条/事件|B_D2 按条/事件|B_R→B_D2 事件差 [95%]|','|---:|---|---:|---|---|---|---|---|']
for L in leads:
 for scope in ('pooled','within_site'):
  for k in (.01,.05,.10):
   subset=top[(top.lead_min==L)&(top.scope==scope)&(top.k.round(4)==k)].set_index('method')
   v=lambda m:f"{fmt(subset.loc[m,'rows'])}/{fmt(subset.loc[m,'events'])}"
   x=subset.loc['B_R_to_B_D2']; sec.append(f'|{L}|{scope}|{int(k*100)}%|{v("B")}|{v("B_D")}|{v("B_R")}|{v("B_D2")}|{fmt(x.events)} [{fmt(x.events_lo)}, {fmt(x.events_hi)}]|')
sec+=['','随机按条期望为实际报警条数/检验总条数（名义 k）；按事件随机期望按每个事件的评分行数 n_e，用超几何 1−C(N−n_e,K)/C(N,K) 平均（原表 random_events，点值可引用）。站内独立配额的随机期望应对每站事件的 n_e、N_s、K_s 分别计算，本报告不把 pooled 期望挪作站内期望。','','### 事后 10-28 B_D2 相对纯持续性 P','','相对差 (MAE_B_D2−MAE_P)/MAE_P，同日配对自助重抽；这不是冻结主判 D_B。','|L min|相对差 [95%]|n|','|---:|---:|---:|']
for L,r in rel.iterrows():sec.append(f'|{L}|{fmt(r.B_D2_vs_P)} [{fmt(r.lo)}, {fmt(r.hi)}]|{int(r.n)}|')
sec+=['','### Δz 与地形：行加权合计','','全量分站 MAE 见 output_final/by_site_delay4.csv；以下每类三站，七/五站两组按行数加权合计。','|L min|组|站数|评分行 n|MAE B / B_D|MAE B_R / B_T0 / B_D2|','|---:|---|---:|---:|---|---|']
for _,r in groups.iterrows():sec.append(f'|{int(r.lead_min)}|{r.group_type}:{r.group}|{int(r.stations)}|{int(r.n)}|{fmt(r.MAE_B)} / {fmt(r.MAE_B_D)}|{fmt(r.MAE_B_R)} / {fmt(r.MAE_B_T0)} / {fmt(r.MAE_B_D2)}|')
sec+=['','### τ 网格与转折','','τ 全表见 supplement/tau.csv，下面各延迟各方法落在端点的站数；训练期选择的 τ 实际来源 pairs/models.json，而非 train_summary。上端截断表示没有在当前网格内选出更短衰减；不能由此证明更优 τ。','|延迟 h|融合方法|τ=15 站|τ=480 站|其余 τ min（站数）|','|---:|---|---:|---:|---|']
for (delay,method),h in tau.groupby(['delay_h','method']):
 inner=h[~h.endpoint].tau_min.value_counts().sort_index();sec.append(f'|{delay}|{method}|{sum(h.tau_min==15)}|{sum(h.tau_min==480)}|{", ".join(f"{int(v)}:{int(n)}" for v,n in inner.items()) or "无"}|')
sec+=['','情景 B 的 B_R/B_T0/B_D2 的 τ 均在上端 480 min，训练网格并未在范围内选出衰减时间；B_R 对 P 的长提前量比较受此设计限制。','',
'转折（合并 MAE，第一档 MAE_X≤MAE_P）：']
for m in ('F','F_D','B','B_D','B_R','B_T0','B_D2','T0','D2'):
 L=next((L for L in leads if main.loc[(L,'MAE_'+m),'point']<=main.loc[(L,'MAE_P'),'point']),None)
 sec.append(f'{m}：{f"{L} min" if L is not None else "0–6 h 内未追平"}。')
sec+=['情景 B 的逐层 T0、D2 在 0–6 h 内均未追平 P（其融合形式 B_T0、B_D2 在 10 min 档即 ≤P，靠的是持续性权重）。','','### 覆盖率：逐站披露','','完整逐站×九提前量×B/B_D/B_D2×80%/90% 点值及样本数见 output_final/coverage_delay4.csv；supplement/coverage_summary.csv 汇总每方法×名义水平的逐站最低/最高。以下列 360 min 的逐站覆盖率以显示合并值不能代替单站可靠性。瑞士冷季全部标为“非对流”是假设，不支持单站风险表述。','|站|B_D2 90%|B_D2 80%|n|','|---|---:|---:|---:|']
for _,r in coverage[(coverage.lead_min==360)&(coverage.site!='all')&(coverage.method=='B_D2')&(coverage.nominal==90)].iterrows():
 r80=coverage[(coverage.lead_min==360)&(coverage.site==r.site)&(coverage.method=='B_D2')&(coverage.nominal==80)].iloc[0]
 sec.append(f'|{r.site}|{fmt(r.coverage)}|{fmt(r80.coverage)}|{int(r.n)}|')
sec+=['','### 冻结边界、归档与限制','','训练拟合只使用训练期行；观测文件在 10-28 08:52 起已含检验期，训练阶段曾整文件读入再按日期切片，不能写“检验期从未读取”。检验期 GFS 取数与评分均在 14:04 生效冻结后。p_observed_utc 在构造上等于 issue，守卫该分支恒成立，不能作为独立防泄漏证明。第 8 节是 14:02 检验期 GFS 取数前追加的补定，旧预注册哈希已被新哈希 e12033b5… 取代；主判定义未变。','',
'BEH 2024-03-08 18:40 至 03-11 08:50（UTC）观测缺测 374 条（由 obs_source_20261028.tgz 程序核出），检验期 BEH 每档评分行 2122–2110，少于其余站均值 2179–2173（output_final/by_site_delay4.csv）。评分曾启动三次，前两次中断，delay4 中间表与终表逐值相同；最终以 score.exit=0 的终表为准。重建评分与冻结 main.csv 逐值比对的容差及最大差见 supplement/parity.json；完整 GFS 包与三档预测归档清单见 supplement/archive_manifest.csv。','',
'局限：GFS 4 h 发布延迟是假设，3/6 h 同号不验证它；P 假定 issue 时刻末尾的观测零延迟可得，10 min 尤其受影响。强风阈值使用被留出站本人的训练期 P95，与“无本站历史”的严格部署设定不一致，只作为副指标。日块自助不覆盖天气尺度的多日相关；10 min D_B 上界尤其靠近零。6 h 的 bucket0 属构造性空档；当前 structural_empty 脚本按训练集零样本判定，没有独立判定构造性。接口“c1<c2”第二转折口径未列入 M6 预注册，不事后补。站点差异与地形不作因果归因。','']
(R/'results.md').write_text(base+intro+'\n'.join(sec)+'\n')
# archive manifest: every rebuilt/archived artifact with sha256 and byte size
import hashlib
man=[]
for relpath in [R/'pairs/test_predictions_delay3.parquet',R/'pairs/test_predictions_delay4.parquet',R/'pairs/test_predictions_delay6.parquet',R/'pairs/test_gfs_full_20261029.tgz',S/'m6_postreview.py',S/'m6_rebuild_core.py',S/'auc_site_ci.csv',S/'topk_corrected.csv',S/'groups.csv',S/'site_mae.csv',S/'B_D2_vs_P.csv',S/'tau.csv',S/'coverage_summary.csv',S/'parity.json',S/'rebuilt_main.csv']:
    man.append(dict(path=str(relpath.relative_to(R)),bytes=relpath.stat().st_size,sha256=hashlib.sha256(relpath.read_bytes()).hexdigest()))
pd.DataFrame(man).to_csv(S/'archive_manifest.csv',index=False)
print('REPORT',len(sec),'lines',len((R/'results.md').read_text().splitlines()),'manifest',len(man))
