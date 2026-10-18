"""Render immutable report from measured metrics.json; fail if target exists."""
import json
from pathlib import Path
R=Path(__file__).resolve().parent;D=json.loads((R/'metrics.json').read_text());A=json.loads((R/'audit.json').read_text())
out=R/'results.md'
if out.exists():raise FileExistsError(out)
rec=D['records'];gate=D['gates'];fmt=lambda x:f'{x:.3f}'
lines=['# A1 巴黎激光雷达短期检验（2023-06—2024-03）','',
'一句结论：选择期按预定 24 h MAE 选中 GFS 直接 100 m 风，而非 AI；该 GFS 方法在留月检验中三项数值门槛均过，但不能据此宣称“AI 城区飞行高度预报可用”。AI 与 GFS 在本样本差距小；高度换算的原始误差敏感，线性 MOS 后固定倍数换算互相不可辨。',
'', '## 预定判据（PALUPD 111 m AGL，所选 GFS/direct100；检验为留一月交叉）','',
'|条件|点估计|按验证日 bootstrap 95% 区间|预定边界|判定|','|---|---:|---:|---:|---|']
for lead in (24,48):
 for base,cn in [('persistence','持续性'),('climatology','非分月 UTC 小时气候值')]:
  x=gate[str(lead)][base]
  lines.append(f"|{lead} h MAE 相对{cn}改善|{100*x['improvement']:.1f}%|{100*x['ci95'][0]:.1f}%—{100*x['ci95'][1]:.1f}%|≥15%|{x['status']}；n={x['n']}|")
x=gate['auc8_24h'];lines.append(f"|24 h ≥8 m/s 逻辑回归 ROC AUC|{x['auc']:.3f}|{x['ci95'][0]:.3f}—{x['ci95'][1]:.3f}|≥0.85|{x['status']}；事件 {x['n_events']}/{x['n']}|")
lines+=['','形式上 24 h、48 h 的两个基线比较与 AUC 均通过，区间没有跨界；但这项“预选主方法”是 GFS，不是 AI，故科学目标“AI 可用”仍未被这些判据证明。夏季选择集仅用于预选源×换算，评估集 2023-09—2024-03 每折只用其余月拟合分站/门/时效线性订正、统计比、概率与气候值；留出月没有进入折内训练。预选时为了符合给定设计，在夏季同集拟合、同集 MAE 排序（乐观偏差）；主方法选择结果不可用评估集反选。',
'', '## 主表：PALUPD（每源每时效均为相同四源可得时刻，111 m，n=317/时效）','',
'|源|换算|24 h 原始 MAE|24 h MOS MAE|48 h 原始 MAE|48 h MOS MAE|24 h AUC8|','|---|---|---:|---:|---:|---:|---:|']
for src in ('FOUR_v200_GFS','GRAP_v100_GFS','PANG_v100_GFS','GFS'):
 for method in (('direct100','log_z0_0p03','power_alpha_0p2','stat_ratio') if src in ('FOUR_v200_GFS','GFS') else ('log_z0_0p03','power_alpha_0p2','stat_ratio')):
  v={lead:next(q for q in rec if q['station']=='PALUPD' and q['target_agl']==100 and q['source']==src and q['method']==method and q['lead_h']==lead) for lead in (24,48)}
  lines.append(f"|{src}|{method}|{fmt(v[24]['raw_mae'])}|{fmt(v[24]['mae'])}|{fmt(v[48]['raw_mae'])}|{fmt(v[48]['mae'])}|{fmt(v[24]['auc8'])}|")
lines+=['','24 h 选择集前四种主候选的最低订正 MAE：GFS/direct100 1.264 m/s；GraphCast 10 m 换算 1.296、Pangu 1.320、FCNv2 1.370 m/s；故主方法选 GFS。留月检验期 GraphCast/log_z0_0p03 与 GFS/direct100 24/48 h 分别为 1.167/1.267 与 1.186/1.324 m/s，差值为 −0.019/−0.057 m/s（仅描述，不能在检验期重选 GraphCast 并认定其达标）。',
'', '## 高度换算、161 m 与郊区对照','',
'在 PALUPD 111 m，GFS 的 24 h 原始 MAE：100 m 直接 1.804、10 m×对数律(z0=0.03 m) 1.268、幂律(alpha=0.2) 1.462、训练月统计比 1.303 m/s。假设敏感性 z0=0.3、alpha=0.14/0.3 的原始 MAE 分别为 1.585、1.269、2.549 m/s。MOS 后所有“10 m×固定分站常数”的 MAE 都约 1.182 m/s，因为自由截距与斜率吸收了固定倍率；仅直接 100 m 的独立输入有区别（1.186）。因此不能据这套线性 MOS 排出对数律/幂律/统计比孰优，也不能从订正后小差距否定原始换算的不确定性。',
'PALUPD 161 m 有效配对每源/时效 n=316；GFS 的直接 100 m 风（未外推到 161 m，存在名义高度错配）MOS 后 24/48 h MAE=1.113/1.286 m/s，仅描述、不参与判据。PAARBO（50/100/150 m）、PACHEM（100/150 m）、PASIRT（仅 150 m）的逐站对照见 metrics.json `records`；各站缺测时段和可用门不同，不能并表替代 PALUPD 判据。',
'', '## 有效小时与来源','',
'|PALUPD 门|2023-06|07|08|09|10|11|12|2024-01|02|03|','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
for z in (100,150):
 m={v['month']:v['hours'] for v in D['observation_hours_by_month'] if v['station']=='PALUPD' and v['target_agl']==z}
 lines.append('|'+str(111 if z==100 else 161)+' m|'+'|'.join(str(m.get(k,0)) for k in ('2023-06','2023-07','2023-08','2023-09','2023-10','2023-11','2023-12','2024-01','2024-02','2024-03'))+'|')
lines+=['','主站评估期实际仅 2023-09—2024-02 六个有值月，2024-02 只有 139 观测小时，2024-03 零小时；因此不是七个月的独立验证。评分只在 00/12 UTC 起报且 24/48 h 有效时刻、四源共同可得与起报实测可得时做，111 m 两时效各 n=317、159 个验证日。Zenodo L3 QC 的 `altitude` 为海拔，减站点地面高程取得 111/161 m AGL；10 min u/v 中心一小时至少四点矢量平均。50 m 主站无有效门，PAJUSS 有仪器盲区未用。',
'',f"AIWP 每源预期 556 个起报对象，实际 FCNv2 {A['by_source']['FOUR_v200_GFS']['objects']}、GraphCast {A['by_source']['GRAP_v100_GFS']['objects']}、Pangu {A['by_source']['PANG_v100_GFS']['objects']}、GFS {A['by_source']['GFS']['objects']}；2023-10-18 12 UTC FCNv2/Pangu 两档缺失，统一从共同配对剔除。总读取处理墙钟 {A['wallclock_seconds']} s，全球 HDF5 只做远程切片，不保存格点于本地。GFS .idx 请求范围总响应字节见 audit.json；AIWP JSON 中的源对象大小不是实际转移字节，不混写。",'',
'图：methods_mae.png（111 m 各源×换算 24 h MOS MAE）、monthly_mae.png（主方法逐留出月）；图角注均标 Morrison et al. Zenodo 17710093、NOAA/CIRA AIWP 与 NOAA/NCEP GFS AWS。站点级 CSV：paired_station.csv.gz。脚本与来源分别为 run_observations.py、run_forecasts.py、run_verify.py、provenance.md。',
'', '## 局限与判语','',
'单一城区主站、单一城市、约六个月有效评估（月间气候并不全）、2 次/日采样、激光雷达垂直门错配及复杂城市粗糙子层，不能外推到全年、所有街区或无人机运营。阈值 8 m/s 是假设风险档，不是监管限值。概率 AUC 仅衡量排序，不保证概率校准或决策价值。以训练月统计比及简单中性剖面作敏感性，z0、alpha 无 PALUPD 同期独立测量；直接 100 m 场在 111 m 本身有 11 m 名义差。','',
'本轮严格点估计和区间：所选 GFS 方法数值判据都通过，AI 未被预选，不把 GFS 的通过写成 AI 的通过；AI 与 GFS 的检验期差异仅作为探索性对照。结论：城区层值得继续量测与校准，高度换算何者最可靠及 AI 是否真正可用仍不清楚。','']
out.write_text('\n'.join(lines));print(out,len(lines))
