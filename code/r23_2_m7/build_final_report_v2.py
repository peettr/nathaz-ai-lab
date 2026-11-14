#!/usr/bin/env python3
"""Render final_report_v2.md from score_v2 (frozen gate) + score_v3 (six-review 1c1f9228
supplements). No refitting, no hand-typed result numbers. Does not touch final_report.md."""
from pathlib import Path
import csv, json, math, hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
R=Path(__file__).parent
S=R/'score_v2';V=R/'score_v3'
g=json.loads((S/'gate.json').read_text())
assert (S/'score.done').read_text().strip()=='success' and (V/'score.done').read_text().strip()=='success'
summ=json.loads((R/'full_final/summary.json').read_text())
chk=json.loads((V/'check_v2_equal.json').read_text())
with (S/'scores.csv').open() as f: rows=list(csv.DictReader(f))
stations=pd.read_csv(S/'station_mae.csv');terrain=pd.read_csv(S/'terrain_mae.csv')
cond3=pd.read_csv(V/'condition_numbers_v3.csv');b3=pd.read_csv(V/'bootstrap_v3.csv')
coef=pd.read_csv(V/'fx_coefficient_summary.csv');contrib=pd.read_csv(V/'site_contribution.csv')
drop=pd.read_csv(V/'drop_one_site_D.csv');strong=pd.read_csv(V/'strong_wind_rows.csv')
idx={(int(x['fhr']),x['metric']):x for x in rows}
i3={(int(r.fhr),r.metric):r for r in b3.itertuples()}
fh=(6,12,24,48)
assert all(float(idx[h,'D']['hi'])<0 for h in fh) and g['pass'] and not g['stop']
pred=pd.read_parquet(S/'paired_predictions.parquet')
now=datetime.now(ZoneInfo('America/New_York')).strftime('%m-%d %H:%M')
def num(x,d=3):return f'{float(x):.{d}f}'
def ci(x,d=3):return f"{num(x['point'],d)} [{num(x['lo'],d)}, {num(x['hi'],d)}]"
def ci3(r,d=3):return f"{num(r.point,d)} [{num(r.lo,d)}, {num(r.hi,d)}]"
def pct(x):return f'{100*abs(float(x)):.1f}%'
Ds=[float(idx[h,'D']['point']) for h in fh]
dmae=[float(idx[h,'MAE_D2']['point'])-float(idx[h,'MAE_FXD2']['point']) for h in fh]
st=stations.assign(better=stations.MAE_FXD2<stations.MAE_D2)
nb={h:int(st[st.fhr==h].better.sum()) for h in fh}
worse_all=sorted(set.intersection(*[set(st[(st.fhr==h)&~st.better].site) for h in fh]))
worse_any=sorted(set(st[~st.better].site)-set(worse_all))
buf=st[st.site=='BUF'];bufr=((buf.MAE_FXD2/buf.MAE_D2)-1)
tg=terrain.assign(worse=terrain.MAE_FXD2>terrain.MAE_D2)
grp_worse=[f"{r['group']}:{r['class']}" for _,r in tg.groupby(['group','class']).worse.all().reset_index().rename(columns={'level_0':'group'}).iterrows() if r['worse']]
cdm=contrib[contrib.site=='CDM'].share_of_net;imp=contrib[contrib.sum_absdiff_FXD2_minus_D2<0].groupby('fhr').share_of_net.sum()
dr=drop.groupby('fhr').D.agg(['min','max'])
fc=coef[coef.method=='FXD2'];fcn=int(fc.n_negative.sum());fct=int(fc.folds.sum())
ftd=[float(idx[h,'delta_FX-T0_minus_D2']['point']) for h in fh];ftr=[ftd[i]/float(idx[h,'MAE_D2']['point']) for i,h in enumerate(fh)]
auc_d=[float(idx[h,'station_mean_AUC_FXD2']['point'])-float(idx[h,'station_mean_AUC_D2']['point']) for h in fh]
cov80=[float(idx[h,'cover80_FXD2']['point']) for h in fh];cov90=[float(idx[h,'cover90_FXD2']['point']) for h in fh]
L=['# M7 FuXi-CFD 瑞士 12 站全量首试 · 最终评分 v2（六审 1c1f9228 修订）',
f'生成 {now}（本地）；由 `build_final_report_v2.py` 从 `score_v2/`（冻结主判）与 `score_v3/`（六审补充）结果表生成，无手写结果数字。原 `final_report.md` 保留不改。',
'',f"预注册 sha256 `5360c303…d59a`；主判评分 `score_m7_local_v2.py`（`21633d53…`）；补充评分 `score_m7_local_v3.py`（只调用 v2 函数，预测与 v2 最大差 {max(chk['predictions_max_abs_diff_vs_v2'].values()):.1e} m/s，容差 1e-9；D 点值与区间与 v2 一致）。",
f"全量推理 {summ['complete']}/{summ['expected']} 行、失败 {len(summ['errors'])}；新推理 {summ['new_inference_count']} 次，均值 {summ['mean_inference_sec']:.4f} s；墙时 {summ['wall_sec']:.0f} s。训练 {g['train_rows']} 行、检验 {g['test_rows']} 行。",
'','## 结论（裁决后收窄）',
f"在 GFS 0.25° 100 m 风驱动 FuXi-CFD 官方权重（常值 z0=0.01 m、SRTM、UTM 9×9 工程假设）、发布延迟假设 4 h 的配置下，把 FuXi-CFD 站点风 FX 作为一项特征加入 M5 D2（FXD2），瑞士 12 站 2024 年 1–3 月 LOSO **合并检验样本**的 10 分钟平均风速 MAE 在 6/12/24/48 h 四档相对 D2 降 {pct(min(Ds,key=abs))}–{pct(max(Ds,key=abs))}（{min(dmae):.3f}–{max(dmae):.3f} m/s；日块 95% 上界均 <0，只重抽日期、站点固定），按冻结预注册主判通过。",
'限定：',
f"- 增量不均：改善站数 {'/'.join(str(nb[h]) for h in fh)}（/12，按 fhr 6/12/24/48）；四档都变差：{'、'.join(worse_all)}（另 {'、'.join(worse_any) or '无'} 在部分时效变差），BUF 变差 {100*bufr.min():.0f}%–{100*bufr.max():.0f}%；四档都变差的分组：{'、'.join(grp_worse)}（每组 3–5 站，只报数字不作组间推断）。",
f"- CDM 一站占合并净下降 {100*cdm.min():.0f}%–{100*cdm.max():.0f}%，改善站之和为净值的 {imp.min():.2f}–{imp.max():.2f} 倍；但去掉任一站后合并 D 仍为 {dr['min'].min():.4f} 至 {dr['max'].max():.4f}，全部 <0。",
f"- FX 的作用方向：FXD2 中 FX 系数 {fcn}/{fct} 折为负（{fc['min'].min():.3f} 至 {fc['max'].max():.3f}）；单用 FX 的线性迁移 FX-T0 比 D2 差 {min(ftd):.3f}–{max(ftd):.3f} m/s（{100*min(ftr):.0f}%–{100*max(ftr):.0f}%）。FX 在本配置里只作为与 R、V1 组合的修正项起作用，不能读成 FuXi-CFD 风对站点风的正向逼近。",
f"- 强风与区间：站内等权 AUC 的 FXD2−D2 点值 {', '.join(f'{x:+.4f}' for x in auc_d)}，无配对区间，写作「无改进证据」；FXD2 名义 80%/90% 区间实际覆盖 {min(cov80):.3f}–{max(cov80):.3f} / {min(cov90):.3f}–{max(cov90):.3f}，低于名义。",
'- 预注册 7.6 延迟 6 h 重选运行敏感性：进行中（`delay6_v2/`，训练检验都重选并重拟合），完成前不得称对发布延迟稳健或预注册全部交付。',
'- 不外推到 FuXi-CFD 本身、ERA5 驱动或其他地区。',
'','## 主判', 'D(L)=(MAE_FXD2−MAE_D2)/MAE_D2；检验日（valid_end 的 UTC 日）整块重抽 1000 次（种子 23050704+fhr），区间 = [Q0.025, Q0.975]（nanquantile）；L=fhr−4 h。',
'| fhr / L (h) | n / 日 | D2 MAE (m/s) | FXD2 MAE (m/s) | D(L) [95%] | 判定 |', '|---|---:|---:|---:|---:|---|']
for h in fh:
 x=idx[h,'D'];L.append(f"| {h} / {h-4} | {x['n']} / {x['days']} | {num(idx[h,'MAE_D2']['point'])} | {num(idx[h,'MAE_FXD2']['point'])} | {ci(x,4)} | 更好（上界<0） |")
L+=['','## 时间守卫（六审必须改 2）',
'预注册 §3 要求守卫与特征用同一份原始时间戳，「不得先把 info_cutoff 赋成 issue 再检查」。M5 配对归档没有 issue/cutoff 列，v2 由 init+4 h 构造两列后再断言，两条断言恒真，**未满足 §3 该条的字面要求**，不构成独立的发布时间核验。两种读法并列：',
'- 严格读法：冻结评分脚本在归档数据上不能运行（`score/score.failed`，KeyError: issue_utc），按冻结脚本无分数。',
'- 宽松读法：issue=init+4 h 即 §3 写定的定义（与 M5 `m5_score.py` 同构造），拟合、MAE、重抽与判据代码未改，v2 主判通过。',
'不泄漏的依据来自构造本身而非守卫：FX 与 D2 特征只取同一 init 运行的 GFS 场，不读观测；训练行 valid_end<2024-01-01、检验行 issue≥2024-01-01。',
'','## 共线性与去截距（六审必须改 3）']
c=cond3
L.append(f"含截距条件数：D2 {c.cond_D2_int.min():.3e}–{c.cond_D2_int.max():.3e}，FXD2 {c.cond_FXD2_int.min():.3e}–{c.cond_FXD2_int.max():.3e}；去截距（保留四类哑元）：D2 {c.cond_D2_noint.min():.3e}–{c.cond_D2_noint.max():.3e}，FXD2 {c.cond_FXD2_noint.min():.3e}–{c.cond_FXD2_noint.max():.3e}。")
L.append('含截距矩阵在精确算术下奇异，数值条件数只表示「≥1e16 量级、秩亏」，具体数值随 BLAS/舍入变化（v2 记录 1.867e18–1.173e19，v3 本机重算为上列），不作比较。')
L.append('去截距 D：'+'；'.join(f'fhr{h} {ci3(i3[h,"D_noint"],5)}' for h in fh)+'。')
L.append('截距等于四个互斥穷尽哑元之和，去截距与原设计张成同一列空间，`lstsq` 取最小范数解，故预测与 D 一致是重参数化的必然结果，**不是对 FX 与 D2 特征共线性的检验**；截距与各地形哑元的单个系数不可辨识、不作解读。')
L+=['','## 副指标：配对 MAE 差 (m/s)','负值表示前者误差较小；日块区间。','| fhr | FX0−R | FX-T0−T0 | FX-T0−D2 | (M+D1+FX)−(M+D1) |','|---|---:|---:|---:|---:|']
for h in fh:L.append('| '+str(h)+' | '+' | '.join(ci(idx[h,m]) for m in ('delta_FX0_minus_R','delta_FX-T0_minus_T0','delta_FX-T0_minus_D2','delta_M+D1+FX_minus_M+D1'))+' |')
L+=['','## FX 系数（`score_v3/fx_coefficient_summary.csv`）','| fhr | 方法 | 折数 | 负系数折数 | 最小 | 中位 | 最大 |','|---|---|---:|---:|---:|---:|---:|']
for r in coef.itertuples():L.append(f'| {r.fhr} | {r.method} | {r.folds} | {r.n_negative} | {r.min:.3f} | {r.median:.3f} | {r.max:.3f} |')
L+=['','## 分站 MAE (m/s) 与对净降的贡献','每格 D2 / FXD2 / FX0；末列为 fhr6 该站 Σ(|e_FXD2|−|e_D2|) 占合并净变化的份额（正=贡献于下降）。','| 站 (类, Δz m) | fhr6 | fhr12 | fhr24 | fhr48 | fhr6 份额 |','|---|---:|---:|---:|---:|---:|']
for site in sorted(stations.site.unique()):
 d={int(r.fhr):r for r in stations[stations.site==site].itertuples()};v=d[6]
 sh=float(contrib[(contrib.fhr==6)&(contrib.site==site)].share_of_net.iloc[0])
 L.append(f"| {site} ({v.terrain}, {v.dz:.1f}) | "+' | '.join('/'.join(num(getattr(d[h],'MAE_'+m),2) for m in ('D2','FXD2','FX0')) for h in fh)+f' | {sh:+.2f} |')
L+=['','去一站合并 D（`score_v3/drop_one_site_D.csv`）：'+'；'.join(f'fhr{h} [{dr.loc[h,"min"]:.4f}, {dr.loc[h,"max"]:.4f}]' for h in fh)+'。']
L+=['','## 地形和高差分组 MAE (m/s)','每格 D2 / FXD2 / FX0；只报数字。','| 组 | fhr6 | fhr12 | fhr24 | fhr48 |','|---|---:|---:|---:|---:|']
for grp in ('terrain','dz'):
 for name in (('pass','plateau','ridge','valley') if grp=='terrain' else ('positive','negative')):
  d={int(r.fhr):r for r in terrain[(terrain.group==grp)&(terrain['class']==name)].itertuples()}
  L.append(f'| {grp}:{name} ({d[6].stations}站) | '+' | '.join('/'.join(num(getattr(d[h],'MAE_'+m),2) for m in ('D2','FXD2','FX0')) for h in fh)+' |')
L+=['','## 强风（站点原生 10 分钟训练 P95）','AUC 站内 12 站等权平均（主口径）/ 跨站合并（描述性，不与站内口径混读）。','| fhr | D2 站内 / 合并 | FXD2 站内 / 合并 | FX0 站内 / 合并 |','|---|---:|---:|---:|']
for h in fh:L.append('| '+str(h)+' | '+' | '.join(ci(idx[h,'station_mean_AUC_'+m])+' / '+ci(idx[h,'AUC_'+m]) for m in ('D2','FXD2','FX0'))+' |')
L+=['','强风事件行 MAE 与偏差（`score_v3/strong_wind_rows.csv`）：','| fhr | 行数 | D2 MAE | FXD2 MAE | D2 偏差 | FXD2 偏差 |','|---|---:|---:|---:|---:|---:|']
for r in strong.itertuples():L.append(f'| {r.fhr} | {r.n_event_rows} | {r.MAE_D2:.3f} | {r.MAE_FXD2:.3f} | {r.bias_D2:+.3f} | {r.bias_FXD2:+.3f} |')
L+=['','Top-k：每时效全网行按预测排序；按条=捕获事件行/全体事件行；按事件=被捕获事件 ID/全体事件 ID。**按事件区间**：v2 在重抽时未区分同一日块的重复副本（六审必须改 4），v3 对每个副本的 event_id 加副本后缀后重算；两列并列，以 v3 为准。','| fhr | k | 方法 | 按条 [v2] | 按事件 [v2 区间] | 按事件 [v3 区间] | 随机期望 按条 / 按事件 |','|---|---:|---|---:|---:|---:|---:|']
for h in fh:
 d=pred[pred.fhr==h];N=len(d);ec=d.loc[d.event].groupby('event_id').size().to_numpy();E=len(ec)
 for k in (1,5,10):
  K=max(1,math.ceil(N*k/100))
  exp=sum(-math.expm1(sum(math.log1p(-int(m)/(N-i)) for i in range(K))) if N-int(m)>=K else 1.0 for m in ec)/E
  for m in ('D2','FXD2','FX0'):
   L.append(f'| {h} | {k}% | {m} | {ci(idx[h,f"Top{k}_"+m])} | {ci(idx[h,f"eventTop{k}_"+m])} | {ci3(i3[h,f"eventTop{k}_"+m])} | {K}/{N}={K/N:.4f} / {exp:.4f}（E={E}） |')
L.append('按事件随机期望 = (1/E)·Σ_e[1−C(N−m_e,K)/C(N,K)]，m_e 为事件 e 的行数。')
L+=['','## 预测区间覆盖率','训练期其他 11 站残差分位数造区间；瑞士冷季全归「非对流大风」（假设），灾种只有一类。','| fhr | D2 80% | FXD2 80% | D2 90% | FXD2 90% |','|---|---:|---:|---:|---:|']
for h in fh:L.append('| '+str(h)+' | '+' | '.join(ci(idx[h,f'cover{k}_'+m]) for k in (80,90) for m in ('D2','FXD2'))+' |')
L+=['','## 实现说明与未完成项',
'- fhr48 的 GFS 时间插值用 f045–f048（f048 前为三小时输出，沿用 M5 `m5_training.py`），不是预注册字面的「相邻整点」f047–f048。',
'- 四档区间各自 95%，非联合覆盖；判据为「至少一档」，四档均过。',
'- 预注册 7.6 延迟 6 h：进行中（`delay6_v2/README.md`，实现细则与脚本 sha256 在读检验期前冻结）。',
'- Colab 实际 CU 无会话级账单，不可独立核算；首项按 35036 行外推的值只是事前预测；0 SU。',
'- 工程假设：z0=0.01 m 常值、UTM ±4 km/1 km 9×9 粗格、偶数网格中心取 (149,149)；GFS 驱动不等于论文 ERA5 驱动。']
out=R/'final_report_v2.md'
assert not out.exists(),'do not overwrite'
out.write_text('\n'.join(L)+'\n')
print(out,'sha256',hashlib.sha256(out.read_bytes()).hexdigest())
