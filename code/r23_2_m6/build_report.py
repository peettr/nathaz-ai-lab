"""Format archived M6 outputs; no fitting or scoring."""
import csv, json, pathlib, datetime, zoneinfo, collections
root=pathlib.Path(__file__).parent
out=root/'output_final'
rows=list(csv.DictReader(open(out/'main.csv')))
by={(int(r['delay_h']),int(r['lead_min']),r['metric']):r for r in rows}
leads=[10,20,30,60,120,180,240,300,360]
assert set(int(r['delay_h']) for r in rows)=={3,4,6}
assert set(int(r['lead_min']) for r in rows)==set(leads)
assert all(float(by[(4,L,m)]['hi'])<0 for L in leads for m in ('D_A','D_B'))
gate=json.load(open(out/'gate.json'))
assert gate['A_pass'] and gate['B_pass'] and not gate['stop']
fmt=lambda x:f'{float(x):.4f}'
ci=lambda r:f"{fmt(r['point'])} [{fmt(r['lo'])}, {fmt(r['hi'])}]"
now=datetime.datetime.now(zoneinfo.ZoneInfo('America/New_York')).strftime('%m-%d %H:%M EDT')
s=[f'# R23.2-04 M6 整链分段增量首试 · 结果（{now}）','',
'仅限这套 GFS 0.25° + 站点海拔插值线性回归 + 指数融合配置、瑞士冻结 12 站、2023-10–12 训练与 2024-01–03 检验。GFS 发布延迟 4 h 未经实测验证，是假设。','',
'## 冻结主判（delay 4 h）','',
'D_A=(MAE_B_D−MAE_B)/MAE_B；D_B=(MAE_B_D2−min(MAE_B_R,MAE_B_T0))/min(MAE_B_R,MAE_B_T0)，每次日块重抽重新选较好基线。95% 区间：同一检验日的 12 站整块重抽 1000 次。下表为点值 [下界, 上界]，无量纲。数据：output_final/main.csv；判定：output_final/gate.json。','',
'|提前量 min|A|B|','|---:|---:|---:|']
for L in leads:s.append(f"|{L}|{ci(by[(4,L,'D_A')])}|{ci(by[(4,L,'D_B')])}|")
s+=['','两个主判均通过：每个提前量的上界均小于 0，预注册止损未触发。此为本配置、本样本的平均风速 MAE 判据，不代表强风预警或单站可靠性。','',
'## 各层 MAE 与分段配对差','',
'完整九档 MAE 与区间、十条相邻/指定层配对差及日块区间见 output_final/main.csv（metric=MAE_*、delta_MAE_*）。以下按方法列九档 MAE 点值，单位 m/s，列顺序为 10/20/30/60/120/180/240/300/360 min。','']
for m in ('P','R','F','F_D','B','B_D','T0','D2','B_R','B_T0','B_D2'):
 s.append(m+': '+', '.join(fmt(by[(4,L,'MAE_'+m)]['point']) for L in leads))
s+=['','## 发布延迟敏感性（重新选择运行后整套重算）','','下表每格为九档 D 的点值及 95% 区间；对应 output_final/main.csv。','']
for delay in (3,6):
 s += [f'延迟 {delay} h：','|提前量 min|A|B|','|---:|---:|---:|']
 for L in leads:s.append(f"|{L}|{ci(by[(delay,L,'D_A')])}|{ci(by[(delay,L,'D_B')])}|")
 s.append('')
s+=['6 h 的 0–6 h 模式时效档按预注册第 8 节结构性零样本补定跳过；按原判据 6 h 敏感性不可计算。此次是在检验期读取前补定，不作为事后检验结果修改。','',
'## 副指标与检查点','',
'逐站 12 站 MAE、地形类型及 Δz>0/≤0 分组可由 output_final/by_site_delay4.csv（site, terrain, dz_positive）逐行核验；地形类与分组仅报数据，不归因。',
'站内等权与合并强风 AUC 的点值和日块区间：output_final/secondary_auc_delay4.csv；按条与按事件 Top-k（1%、5%、10%）、日块区间及随机期望：output_final/topk_delay4.csv。强风阈值取各站训练期原生十分钟观测 P95。','80%/90% 名义覆盖率按站和合并的表：output_final/coverage_delay4.csv；瑞士冷季全归非对流是假设。',
'F 与 F_D 追平 P 的最短提前量、训练选择的各方法 τ：见下方程序核算及 pairs/train_summary_section8.json。端点 τ=15 或 480 min 须按网格边界读，不作外推。','','## 归档与限制','',
'训练、检验 GFS 检查点及训练系数见 pairs/；评分退出码 score.exit=0，日志 score_1028_204904.log。Colab 会话 r23-2-m6-cpu 已停止。共享账户并行有其他会话，无本任务独立 CU 账单，不报告精确实耗；首项预算投影见 EXPERIMENT_CARD.md。',
'首次读检验期前冻结的评分脚本与配置 SHA256 见 EXPERIMENT_CARD.md③；本报告为归档格式整理，不修改冻结评分器或预注册。','']
# Derive crossover from frozen MAE table.
for x in ('F','F_D'):
 t=next((L for L in leads if float(by[(4,L,'MAE_'+x)]['point'])<=float(by[(4,L,'MAE_P')]['point'])),None)
 s.append(f'本次合并 MAE 点值中 {x} 追平 P 的最短提前量：{t if t is not None else "九档内无"} min（output_final/main.csv）。')
(root/'results.md').write_text('\n'.join(s)+'\n')
print('wrote',root/'results.md','rows',len(rows),'gate',gate['A_pass'],gate['B_pass'])
