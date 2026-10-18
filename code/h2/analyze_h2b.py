#!/usr/bin/env python3
"""Read-only re-scoring of precomputed H2d LOO land-site peaks; no refitting."""
import csv, json, math
from pathlib import Path
R=Path(__file__).resolve().parent
P=R/'peaks_clean_h2d.csv'
M=R/'metrics_clean_h2d.json'
REG=['DELTA','ZETA','IDA','IAN','NICOLE','IDALIA','DEBBY','HELENE','MILTON']
SEEN=['NICHOLAS','BERYL']
BASE=['idw','ok75','okfit']
FUSE=['era_resok75','era_resokfit','holland_resok75','holland_resokfit']
with P.open(newline='') as f: rows=[r for r in csv.DictReader(f) if r['pool']=='land']
old=json.loads(M.read_text())['land_metrics']
def evaluate(rows):
    n=len(rows)
    scores={}
    for k in BASE+FUSE:
        err=[float(r[k])-float(r['obs']) for r in rows]
        scores[k]={'rmse':math.sqrt(sum(v*v for v in err)/n) if n else None,
                   'bias':sum(err)/n if n else None,
                   'mae':sum(map(abs,err))/n if n else None}
    a=min(BASE,key=lambda k:scores[k]['rmse'] if n else math.inf)
    b=min(FUSE,key=lambda k:scores[k]['rmse'] if n else math.inf)
    gain=1-scores[b]['rmse']/scores[a]['rmse'] if n and scores[a]['rmse'] else None
    wins=sum(abs(float(r[b])-float(r['obs']))<abs(float(r[a])-float(r['obs'])) for r in rows)
    eligible=n>=8
    verdict=('强风站值得融合' if gain>=.2 and wins/n>=2/3 else '有条件' if gain>=.1 or wins/n>=2/3 else '插值够用') if eligible else '不可评'
    return {'stations':n,'evaluable':eligible,'baseline':a,'fusion':b,'baseline_rmse':scores[a]['rmse'],
            'fusion_rmse':scores[b]['rmse'],'gain':gain,'wins':wins,'verdict':verdict,'methods':scores}
main={e:evaluate([r for r in rows if r['event']==e]) for e in REG+SEEN}
main['COMBINED']=evaluate([r for r in rows if r['event'] in REG+['NICHOLAS']])
strong={e:evaluate([r for r in rows if r['event']==e and float(r['obs'])>=12]) for e in REG+SEEN}
strong['INDEPENDENT_ALL9']=evaluate([r for r in rows if r['event'] in REG and float(r['obs'])>=12])
evaluable=[e for e in REG if strong[e]['evaluable']]
strong['INDEPENDENT_EVALUABLE']=evaluate([r for r in rows if r['event'] in evaluable and float(r['obs'])>=12])
assert set(old['COMBINED']['methods'])>=set(BASE+FUSE)
for e in REG+SEEN+['COMBINED']:
    prior=old[e]
    assert main[e]['stations']==prior['stations'],(e,'count')
    assert main[e]['baseline']==prior['baseline'] and main[e]['fusion']==prior['best_fusion'],(e,'selection')
    assert abs(main[e]['gain']-prior['gain'])<1e-10,(e,'gain')
    assert main[e]['wins']==prior['station_wins'],(e,'wins')
assert sum(strong[e]['stations'] for e in REG)==strong['INDEPENDENT_ALL9']['stations']
assert sum(strong[e]['stations'] for e in evaluable)==strong['INDEPENDENT_EVALUABLE']['stations']
out={'metadata':{'pre_registration':'prereg_h2b.md','source_peaks':'peaks_clean_h2d.csv (read-only)','source_audit':'station_clean_h2d.csv','wind':'METAR hourly sustained, not gust','UTC':True,'strong_threshold_mps':12,'independent_events':REG,'seen_events':SEEN,'evaluable_independent_strong_events':evaluable,'eligibility_min_stations':8,'main_combined_includes_nicholas_excludes_beryl':True,'independent_excludes_both_seen_events':True,'method_selection':'minimum pooled peak RMSE within each subset (post-hoc, optimistic)'},'primary':main,'strong':strong}
(R/'metrics_h2b.json').open('x').write(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
def cell(x):
    a=x['baseline_rmse'];b=x['fusion_rmse']
    return f"{x['stations']}|{x['baseline']} / {x['fusion']}|{a:.3f} → {b:.3f}|{x['gain']*100:.2f}%|{x['wins']}/{x['stations']}|{x['verdict']}" if a is not None else '0|—|—|—|—|不可评'
lines=['# H2b 强风站副判据：清洗陆地站十事件','',
'2026-10-14；UTC。副判据先写 `prereg_h2b.md`，再对已存在的 H2d 逐站留一峰值表重新分层评分；没有重新运行或调整风场/模型。H2d 全十事件模型预测已先于本次副判据产生，所以这是未按强风子集调参的独立事件检验，而非严格前瞻性预测验证。原结果保留。','',
'## 预定口径','',
'只取 `station_clean_h2d.csv` 清洗后的 land 池、具备原 H2d 覆盖资格的站；水体/平台、重复及可疑坐标站不参与输入、拟合和评价。事件峰值是可观测小时中各方法预测的最大值，强风按同一站实测最大持续风 ≥12 m/s 选择；阵风不入此判据。每事件峰值 RMSE 最小的纯插值（IDW/OK固定/OK拟合）与背景+残差（ERA5/H08，固定/拟合 OK）相比，站点绝对误差严格减小才算胜；至少 8 站可评。收益 ≥20% 且胜站 ≥2/3 判“强风站值得融合”，≥10% 或仅胜站门槛判“有条件”，否则“插值够用”。方法按测试集选优带选择乐观性。', '',
'## 主判据（全部合格陆地站）','','|事件|站数|最佳纯插值 / 最佳融合|峰值 RMSE (m/s)|降幅|胜站|判定|','|---|---:|---|---:|---:|---:|---|']
for e in REG+['NICHOLAS','COMBINED','BERYL']:
    label=e+('（已见过数据，仅供对照）' if e in SEEN else '')
    lines.append(f'|{label}|{cell(main[e])}|')
lines+=['','## 副判据（实测事件峰值持续风 ≥12 m/s）','','|事件|强风站数|最佳纯插值 / 最佳融合|峰值 RMSE (m/s)|降幅|胜站|判定|','|---|---:|---|---:|---:|---:|---|']
for e in REG+['INDEPENDENT_EVALUABLE','INDEPENDENT_ALL9']+SEEN:
    label=e+('（已见过数据，仅供对照）' if e in SEEN else '')
    lines.append(f'|{label}|{cell(strong[e])}|')
lines+=['',f'独立可评强风事件：{", ".join(evaluable) if evaluable else "无"}。少于 8 站的事件不作单事件判定，不计入可评事件合计；九事件全集一行仅描述样本覆盖。主判据 COMBINED 沿原十事件口径包含 Nicholas、不包含 Beryl；独立强风检验排除两者。', '',
'## 参数来源与局限','',
'|参数|来源与性质|','|---|---|',
'|事件、陆地清洗、H08、ERA5、站点覆盖、两种变差函数|复用 `results_clean_h2e.md`、`evaluate_clean_h2d.py` 已缓存输出；75 km、nugget .08、经验拟合范围等均为原 H2 假设，不是文献值；H08 时距/阵风因子沿 B v1 预登记的假设；本轮不调参|',
'|12 m/s、至少 8 站、副判据及胜站规则|本轮 Lead 任务书、`prereg_h2b.md`；在读取本轮强风子集指标前登记；Beryl/Nicholas 已见过数据|',
'|事件峰值时刻|原 H2d 每站方法峰值均在该站有观测的小时取最大值，不一定与实测最大值同时；缺报/截尾站未评分；风强缺测非随机|',
'','此副判据按实测风速条件筛选站点（事后分层），只检验已有合格观测的站，不代表真实全域强风点；事后以评分结果在七个方法中挑优会高估收益；NHC 事后路径及 ERA5 再分析不是实时预报。逐站留一仍有空间邻站，不能外推至大面积断站。数据引用沿 `PUBLIC_CITATIONS.md` 已记的 IEM METAR、ARCO ERA5、ESA WorldCover、NHC/B v1，本轮无新增外部数据。', '',
'脚本 `analyze_h2b.py`；数值及方法逐项评分 `metrics_h2b.json`。原先 H2d 主指标已逐项核对一致。']
(R/'results_h2b.md').open('x').write('\n'.join(lines)+'\n')
print('independent',[(e,strong[e]['stations'],strong[e]['gain'],strong[e]['wins'],strong[e]['verdict']) for e in REG]);print('aggregate',strong['INDEPENDENT_EVALUABLE']['stations'],strong['INDEPENDENT_EVALUABLE']['gain'],strong['INDEPENDENT_EVALUABLE']['wins'],strong['INDEPENDENT_EVALUABLE']['verdict']);print('seen',[(e,strong[e]['stations'],strong[e]['gain'],strong[e]['wins']) for e in SEEN])
