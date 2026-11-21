"""Generate bounded L26.12-03 report from retrieved result tables, never from memory."""
import json, collections, sys
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent
G=json.loads((R/'gate.json').read_text())
lines=['# L26.12-03 汇合后 SAE 出路 A 实测','', '数据来源：ECMWF Pangu-Weather 24 h ONNX；WeatherBench2 ERA5 derived zarr；NOAA NCEI IBTrACS v04r01 NA/WP。原始 step2/step3 的 321 风暴队列与 42 场 t+24 合格队列冻结；本报告由 make_report.py 从 stepA 结果生成。','', '## 层与模型闸门','',f"切点 {G['cut']}，形状 {G['shape']}，首个实际跳连汇合为 /b1/Concat_207_output_0（/b1/Add_6_output_0 与 /b1/Add_55_output_0 拼接）；段 B 边界集合 {G['boundary']}，其中 Constant {G['constants']}，非常量 {G['nonconstant']}。输出相对最大差 {G['rel_maxdiff']}，阈值 <1e-4：{'通过' if G['pass'] else '未通过'}。",'']
L=R/'layout_probe.json'
if L.exists():
 l=json.loads(L.read_text());lines += [f"空间核对：{l['ny']} 行，纬步长 {l['latstep']}°、经步长 {l['lonstep']}°；输入 (20°N,130°E) 局域加 2000 Pa，块 0 响应峰 {l['peaks'][0]}。",'']
F=R/'first50.json'
if F.exists():
 x=json.loads(F.read_text());lines += [f"首 50 时次 {x['seconds']:.1f} s，按已测边际约 {x['seconds']/x['records']:.2f} s/时次；全 321 时次投影约 {321*x['seconds']/x['records']/60:.1f} min（只含激活阶段，不含训练/干预），以实测后预算监控决定是否继续。",'']
C=R/'correlations.json';B=R/'b_results.json';I=R/'interventions.jsonl'
def f(x):return '未评估' if x is None or not np.isfinite(x) else f'{x:.4f}'
def lo(ci):return 0 if ci[0]<=0<=ci[1] else min(abs(ci[0]),abs(ci[1]))
if C.exists():
 c=json.loads(C.read_text());lines += ['## SAE 与相关','',f"SAE 宽 {c['width']}，K={c['K']}；K 选择验证 MSE {c['K_selection_val_mse']}；最终训练重建归一化 MSE={f(c['train_reconstruction_normalized_mse'])}。训练 {c['n_train']} 场，检验 {c['n_test']} 场。",'']
 if B.exists():
  b=json.loads(B.read_text());lines += [f"20 种子 {b['seeds']}；每种子置换 1000 次（全字典最大 |ρ|），风暴自助 5000 次。主读法为检验 95% 区间的 |ρ| 下界 > 置换最大值；并列读法仅将置换阈值换为 95 分位。",'','|属性|特征|训练ρ|检验ρ|95% CI 范围（20种子）|下界−置换最大范围|主读法通过种子数|95分位通过种子数|PCA最优检验|判据②|','|---|---:|---:|---:|---|---|---:|---:|---:|---|']
  for p,rs in c['candidates'].items():
   pc=abs(c['baselines'][p]['pca_test_rho'])
   for r in rs:
    ss=[next(z for z in q['candidates'] if z['feature']==r['feature']) for q in b['expanded'][p]];ds=[z['lower_abs']-q['null']['maximum'] for q,z in zip(b['expanded'][p],ss)]
    cis=[z['ci'] for z in ss]
    lines.append(f"|{p}|{r['feature']}|{f(r['train_rho'])}|{f(r['test_rho'])}|[{f(min(z[0] for z in cis))},{f(max(z[1] for z in cis))}]|[{f(min(ds))},{f(max(ds))}]|{sum(z['main'] for z in ss)}/20|{sum(z['q95_read'] for z in ss)}/20|{f(pc)}|{abs(r['test_rho'])>=pc}|")
  best=max((r for p,rs in c['candidates'].items() for r in rs),key=lambda r:abs(r['test_rho']))
  p=next(p for p,rs in c['candidates'].items() if any(z['feature']==best['feature'] for z in rs));ds=[next(z for z in q['candidates'] if z['feature']==best['feature'])['lower_abs']-q['null']['maximum'] for q in b['expanded'][p]]
  q=np.quantile(ds,[.025,.975]);sep=bool(q[1]<0 or q[0]>0)
  lines += ['',f"判据①主读法：{any(z['main'] for p in b['expanded'] for q in b['expanded'][p] for z in q['candidates'])}；并列 95 分位读法：{any(z['q95_read'] for p in b['expanded'] for q in b['expanded'][p] for z in q['candidates'])}（非替代）。判据②逐特征见上表。否定条件 (i)：最佳检验 |ρ| 特征 {best['feature']}（{p}），20 种子差值 2.5–97.5 分位 [{f(q[0])},{f(q[1])}]，整段同号={sep}。",'']
 else:lines += ['20 种子重采样尚未完成；判据①主读法/并列读法与否定条件 (i) 未评估。','']
else:lines += ['## SAE 与相关','', '未完成训练；判据①②及否定条件 (i) 未评估。','']
lines += ['## 干预','']
if I.exists() and C.exists():
 rows=[json.loads(s) for s in I.read_text().splitlines() if s.strip()]; by=collections.defaultdict(list)
 for r in rows:by[(r['control'],r.get('reference',r['feature']),r['feature'],r['alpha'])].append(r)
 storms={r['sid'] for r in rows if r['control']=='pure_decoder'}; targets=sorted({r['feature'] for r in rows if r['control']=='target'})
 lines += [f"实际记录 {len(rows)} 行，纯解码覆盖 {len(storms)}/42 场，目标特征 {targets}。E=该 α 下 (干预−原预报) 最低 MSL 的风暴中位数（hPa）；E₀=十个同幅度非目标特征各自 |E| 的 95 分位；Δ风速单位 m/s。",'','|目标|α|E hPa|E₀ hPa|比值|随机方向 E hPa|Δ风速中位|发散/总数（全部类型）|单场最大 |ΔMSL| hPa|目标激活场数|','|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
 for j in targets:
  es=[];rat=[];bounds=[]
  for a in (0.,.5,1.5,2.):
   t=by.get(('target',j,j,a),[]);es.append(float(np.median([z['dmsl_hpa'] for z in t])) if t else float('nan'))
   ctl=[np.median([z['dmsl_hpa'] for z in vv]) for (typ,ref,feat,aa),vv in by.items() if typ=='matched' and ref==j and aa==a and len(vv)==len(storms)]
   e0=float(np.quantile(np.abs(ctl),.95)) if ctl else float('nan');rat.append(abs(es[-1])/e0 if e0 else float('nan'))
   rand=by.get(('random_direction',j,j,a),[]);aa=[z for z in rows if z.get('alpha')==a and z.get('control')!='pure_decoder'];dv=sum(bool(z.get('divergent')) for z in aa)
   lines.append(f"|{j}|{a:g}|{f(es[-1])}|{f(e0)}|{f(rat[-1])}|{f(float(np.median([z['dmsl_hpa'] for z in rand])) if rand else None)}|{f(float(np.median([z['dwind_ms'] for z in t])) if t else None)}|{dv}/{len(aa)}|{f(max((abs(z['dmsl_hpa']) for z in t),default=None))}|{len(t)}|")
   if a in (0.,2.) and len(t)==42:
    rng=np.random.default_rng(2612+j+int(a));v=np.abs([z['dmsl_hpa'] for z in t]);med=np.median(rng.choice(v,(5000,len(v)),replace=True),axis=1);bounds.append((a,float(np.median(v)),float(np.quantile(med,.95))))
  assoc=max(((abs(r['train_rho']),p,r['train_rho']) for p,rr in c['candidates'].items() for r in rr if r['feature']==j),default=None)
  monotonic=bool(np.all(np.diff(es)>=0) or np.all(np.diff(es)<=0)) if all(np.isfinite(es)) else False
  direction=bool(np.sign(es[3])==np.sign(assoc[2]) and np.sign(es[0])==-np.sign(assoc[2])) if assoc else False
  gate3=bool(monotonic and direction and min(rat[0],rat[3])>=3)
  lines += [f"特征 {j} 判据③：四点单调 {monotonic}，按训练关联属性 {assoc[1] if assoc else '未定'} 的方向 {direction}，α0/2 比值 {f(rat[0])}/{f(rat[3])}，合格 {gate3}。否定条件 (ii) α0/2 |Δ最低气压| 中位与 95% 自助上界：{bounds if len(bounds)==2 else '未完成42场，不评估'}。",'']
else:lines += ['尚无完整逐场干预，判据③和否定条件 (ii) 未评估。','']
lines += ['## 资源与判定','', '会话：l2612-postmerge-stepA；起始 11-03 10:44 EST。停止时间、Colab usage 前后余额和实耗估计以结算记录为准；账户有并发分配，余额差不能单独归因。本项目的 30 CU 累计截止须与最终时间记录逐项核算。','', '未齐备的判据一律记未评估，不将不确定性当否定；最终值得用/放弃由 Lead 按预注册判据裁定。','', '假设：切点保留各风暴中心 ±5° 的 8 个块 token；内部验证按风暴随机留 20%，TopK 候选训练 2 epoch、最终 5 epoch，AdamW 5e-4；这些沿用 step2 并非文献参数。']
(R/'报告_L26.12-03.md').write_text('\n'.join(lines)+'\n');print('report sections',len(lines))
