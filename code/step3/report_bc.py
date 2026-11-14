"""Derive both immutable cohort intervention tables and B summary from saved rows."""
import json,collections,math,statistics
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;OLD=R.parent/'step2';C=json.loads((OLD/'sae_final/correlations.json').read_text());B=json.loads((R/'b_results.json').read_text());F=np.load(OLD/'sae_final/features.npy');cohort=json.loads((OLD/'cohort_2021.json').read_text());ids={r['sid']:i for i,r in enumerate(cohort)}
def load(p):return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]
old=load(OLD/'interventions_complete.jsonl');new=load(R/'interventions_remaining.jsonl');elig=json.loads((R/'eligibility.json').read_text());expected=set(elig['original']+elig['remaining'])
def ff(v):return '未评估' if v is None or not math.isfinite(float(v)) else f'{v:.4f}'
def lower(ci):return 0 if ci[0]<=0<=ci[1] else min(abs(ci[0]),abs(ci[1]))
lines=['# L26.12-02 出路 B/C 实测','', '数据来源：NOAA NCEI IBTrACS v04r01 NA/WP；WeatherBench2 ERA5 derived zarr（实际至 2021）；ECMWF Pangu-Weather 24h ONNX；第 2 步冻结 SAE 特征与原干预逐行表。所有表格数字由本脚本生成。','', '## B：只读冻结激活的检验','', '与旧程序相同的 200 次置换/1000 次风暴自助（旧种子）逐值复现：'+str(all(v['exact_match'] for v in B['legacy'].values()))+'。新实验的三个种子为 '+str(B['seeds'])+'；各属性 1000 次置换的最大值在 1536 个特征中取最大；5000 次风暴自助的区间下界为不跨零时 min(|端点|)，跨零为 0。主读法要求检验 |ρ|≥0.5 且下界严格大于置换最大值；并列读法仅把该最大值替换为置换最大统计量的 95 分位，并非改动预设判据。','', '|属性|特征|种子|检验 ρ|区间 |ρ| 下界|置换最大|置换 95 分位|主读法①|并列读法①|','|---|---:|---:|---:|---:|---:|---:|---|---|']
for p,runs in B['expanded'].items():
 for run in runs:
  for v in run['candidates']:lines.append('|'+ '|'.join(map(str,[p,v['feature'],run['seed'],ff(v['test_rho']),ff(v['lower_abs']),ff(run['null']['maximum']),ff(run['null']['q95']),'满足' if v['main'] else '不满足','满足' if v['q95_read'] else '不满足']))+'|')
 for j in [v['feature'] for v in runs[0]['candidates']]:
  xx=[next(v for v in a['candidates'] if v['feature']==j)['lower_abs'] for a in runs]
  lines.append(f'{p} / {j}：下界三种子极差 {ff(max(xx)-min(xx))}。')
 xx=[a['null']['maximum'] for a in runs];lines.append(f'{p}：置换最大值三种子极差 {ff(max(xx)-min(xx))}。')
lines+=['','## C：原 30 场与补齐后对照','',f"2021 检验集 {sum(r['year']>=2021 for r in cohort)} 场；原 {len(elig['original'])} 场，新增 {len(elig['remaining'])} 场，缺 t+24 位置 {len(elig['missing'])} 场："+(', '.join(x['sid'] for x in elig['missing']) or '无')+'。新增 SID：'+', '.join(elig['remaining'])+'。','', 'E 为每场 (干预−原预测) 的最低 MSL 差的跨风暴中位数（hPa）；E₀ 为匹配对照每个特征的跨风暴中位 |E| 的 95 分位。风速为同一 5° 窗口最大 10m 风速差（m/s）。方向使用训练相关量的符号，四点单调用跨风暴中位 E；比值门槛看 α=0、2。发散定义为非有限或 |ΔMSL|>50 hPa。α=1 纯解码另列，不同于保留残差的主干预。','']
for name,rows,sids in [('原30',old,set(elig['original'])),('补齐',old+new,expected)]:
 assert set(r['sid'] for r in rows)==sids
 assert len(rows)==len(sids)*131,(name,len(rows),len(sids))
 unique={(r['sid'],r['control'],r['feature'],r['alpha'],r.get('reference')) for r in rows};assert len(unique)==len(rows),(name,len(unique),len(rows))
 gr=collections.defaultdict(list)
 for r in rows:gr[(r['control'],r.get('reference',r['feature']),r['feature'],r['alpha'])].append(r)
 lines+=['',f'### {name}（{len(sids)} 场、{len(rows)} 行）','','|目标特征|α|E hPa|E₀ hPa||E|/E₀|风速 Δ 中位 m/s|目标发散数|匹配发散数|单场最大 |ΔMSL| hPa|激活场数 z>0|','|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
 targets=sorted({r['feature'] for r in rows if r['control']=='target'})
 for j in targets:
  activated=sum(F[ids[s],j]>0 for s in sids)
  association=max(((abs(v['train_rho']),p,v['train_rho']) for p,rr in C['candidates'].items() for v in rr if v['feature']==j),default=None)
  es=[];thresholds=[]
  for a in (0.,.5,1.5,2.):
   target=gr[('target',j,j,a)];assert len(target)==len(sids)
   ee=float(np.median([v['dmsl_hpa'] for v in target]));es.append(ee)
   controls=[float(np.median([v['dmsl_hpa'] for v in vs])) for (kind,ref,c,aa),vs in gr.items() if kind=='matched' and ref==j and aa==a and len(vs)==len(sids)]
   e0=float(np.quantile(abs(np.array(controls)),.95)) if controls else None;thresholds.append(e0)
   ratio=abs(ee)/e0 if e0 and e0>0 else None
   matched=[v for (kind,ref,c,aa),vs in gr.items() if kind=='matched' and ref==j and aa==a for v in vs]
   lines.append('|'+ '|'.join(map(str,[j,a,ff(ee),ff(e0),ff(ratio),ff(np.median([v['dwind_ms'] for v in target])),f"{sum(bool(v.get('divergent')) for v in target)}/{len(target)}",f"{sum(bool(v.get('divergent')) for v in matched)}/{len(matched)}",ff(max(abs(v['dmsl_hpa']) for v in target)),activated]))+'|')
  mono=bool(np.all(np.diff(es)>=0) or np.all(np.diff(es)<=0));direction=bool(np.sign(es[-1])==np.sign(association[2]) and np.sign(es[0])==-np.sign(association[2]));ratios=[abs(es[i])/thresholds[i] if thresholds[i] and thresholds[i]>0 else None for i in (0,3)];gate=mono and direction and all(x is not None and x>=3 for x in ratios)
  lines.append(f'特征 {j}：E={list(map(ff,es))}；单调={mono}，方向={direction}（归属 {association[1]}），α0/α2 比值={list(map(ff,ratios))}，判据③={"满足" if gate else "不满足"}。')
  if j==1004:
   alt=[float(np.median([v['dmsl_hpa'] for v in vs])) for (kind,ref,c,a),vs in gr.items() if kind=='matched' and ref==1004 and c!=270 and a in (0.,2.) and len(vs)==len(sids)]
   for a in (0.,2.):
    alt=[float(np.median([v['dmsl_hpa'] for v in vs])) for (kind,ref,c,aa),vs in gr.items() if kind=='matched' and ref==1004 and c!=270 and aa==a and len(vs)==len(sids)]
    lines.append(f'1004 剔除对照 270 后 α={a:g} 的 E₀={ff(np.quantile(abs(np.array(alt)),.95))} hPa（{len(alt)} 个，敏感性，不替代原对照）。')
 for a in (0.,.5,1.5,2.):
  rr=[v for v in rows if v['alpha']==a and v['control']!='pure_decoder'];lines.append(f'α={a:g}：全目标、匹配与随机方向的发散 {sum(bool(v.get("divergent")) for v in rr)}/{len(rr)}。')
 pure=[v for v in rows if v['control']=='pure_decoder'];lines.append(f'α=1 纯解码 {len(pure)} 场，ΔMSL 中位 {ff(np.median([v["dmsl_hpa"] for v in pure]))} hPa。')
(R/'报告_L26.12-02.md').write_text('\n'.join(lines)+'\n');print('report',len(old),len(new),len(expected))
