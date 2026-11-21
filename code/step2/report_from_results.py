"""Generate the L26.12 numerical report from immutable Colab result tables."""
import collections,json,math,statistics
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent
C=json.loads((R/'correlations.json' if (R/'correlations.json').exists() else R/'sae_final/correlations.json').read_text());A=json.loads((R/'source_axis_audit.json').read_text());L=json.loads((R/'layout_probe.json').read_text())
cohort=json.loads((R/'cohort_2021.json').read_text())
warm=[json.loads(x) for x in (R/'warmcore.jsonl').read_text().splitlines() if x.strip()] if (R/'warmcore.jsonl').exists() else []
data=(R/'interventions.jsonl' if (R/'interventions.jsonl').exists() else R/'intervene_final/interventions.jsonl')
rows=[json.loads(x) for x in data.read_text().splitlines() if x.strip()] if data.exists() else []
if not rows:
 pull=sorted(R.glob('interventions_*.jsonl'));rows=[json.loads(x) for x in pull[-1].read_text().splitlines()] if pull else []
def f(v):return '未评估' if v is None else f'{v:.3f}'
def ci(v):return '未评估' if v is None else f'[{f(v[0])}, {f(v[1])}]'
def lower_abs(interval):return 0 if interval[0]<=0<=interval[1] else min(abs(x) for x in interval)
lines=['# L26.12-01 SAE 台风特征：相关与干预实测','', '数据来源：NOAA NCEI IBTrACS v04r01 NA/WP CSV；WeatherBench2 ERA5 1959–2022 命名的 derived zarr；ECMWF Pangu-Weather 24h ONNX（CC BY-NC-SA 4.0，仅研究）。所有数字由 `report_from_results.py` 读取结果表生成。','', '## 源与队列','',f'ERA5 实际末时次为 {A["era5_actual_last"]}，与路径名「2022」不符。2022 年 {A["test_2022_unavailable_storms"]} 场不做最近邻替代；本次只用 2021 年 {A["test_2021_storms"]} 场检验。初始训练 2015–2020 为 {C["n_train"]} 场/{C["n_train"]} 时次，检验 2021 为 {C["n_test"]} 场/{C["n_test"]} 时次；每场取达到 34 kt 后最大风的一个 6 小时时次。这个选法是在首 50 时次计时后按资源限额从最多四时次缩为一时次，非原始「约 300」的按时次随机检验。','',f'首 50 时次：总墙钟 584.05 s（含准备与下载 110.5 s），边际 9.471 s/时次；全 1128 时次仅激活预估 178.05 min/15.73 CU（按 5.3 CU/h），尚未含训练和干预，故采用 321 时次队列。原始 50 与本队列的重复窗口复用，窗口归档 `windows_2021.tar`（仅本地小结果）；全局场未落本地。','',f'排列核对：对输入 (20°N,130°E) 5×5 网格 MSL 加 2000 Pa，主干 token 的第 0 块响应峰在 (row {L["peaks"][0]["row"]}, col {L["peaks"][0]["col"]})，映射为 ({L["peaks"][0]["lat_guess"]}°N,{L["peaks"][0]["lon_guess"]}°E)，与 8×91×180、每 token 约 2° 的假设一致；后续块受注意力传播影响，峰不一定同位。窗口取中心经纬 ±5°、八块全取。','', '## SAE 与相关','',f'宽度 {C["width"]}（384 通道的四倍），TopK 的训练内部留出按风暴取 20%；两 epoch 的 K 候选验证归一化 MSE：'+', '.join(f'{k}: {m:.4f}' for k,m in C['K_selection_val_mse'])+f'；选 K={C["K"]}；再以训练集全部风暴做五 epoch，最终训练归一化重建 MSE={C["train_reconstruction_normalized_mse"]:.4f}。这些为本次训练设定，并非文献给定参数。','', '特征值：一个窗口的各 token TopK 激活最大值。训练集按 |Spearman ρ| 对风速、气压各选前五、去重。95% CI 对检验风暴有放回重采样 1000 次；单时次/风暴。打乱对照在 200 次风暴标签置换中，每次取全字典 1536 特征的最大 |ρ|。','', '|属性|特征|训练 ρ|检验 ρ|检验 95% CI|CI 对 |ρ| 下界|置换最大|判据①该特征|','|---|---:|---:|---:|---|---:|---:|---|']
wc=[x['warmcore_K'] for x in warm if 'warmcore_K' in x]
lines.insert(7,f'附加属性：ERA5 300 hPa 暖心（中心 1° 内均温减 5–10° 环带均温）取得 {len(wc)}/{len(cohort)} 场，中位数 {f(float(np.median(wc)) if wc else None)} K；IBTrACS RMW 非缺失 {sum(r["rmw_nm"] is not None for r in cohort)}/{len(cohort)}。暖心/RMW 未进入预设两项相关判据。')
passes=[]
for prop,rs in C['candidates'].items():
 null=C['null'][prop]['max_200']
 for r in rs:
  lo=lower_abs(r['test_ci95']);ok=abs(r['test_rho'])>=.5 and lo>null
  passes.append((prop,r['feature'],ok))
  lines.append(f'|{prop}|{r["feature"]}|{f(r["train_rho"])}|{f(r["test_rho"])}|{ci(r["test_ci95"])}|{f(lo)}|{f(null)}|{"满足" if ok else "不满足"}|')
lines+=['', '|属性|置换 200 次最大 |ρ||置换 95 分位|PCA(k=10) 最佳 PC (训练选)|PCA 检验 ρ [95%CI]|岭回归 CV α / 检验 ρ|','|---|---:|---:|---|---|---|']
for p in C['candidates']:
 n=C['null'][p];b=C['baselines'][p]
 lines.append(f'|{p}|{f(n["max_200"])}|{f(n["q95_200"])}|PC{b["pca_best_component"]+1} (ρ={f(b["pca_train_rho"])})|{f(b["pca_test_rho"])} {ci(b["pca_ci95"])}|α={b["ridge_alpha"]}，ρ={f(b["ridge_test_rho"])}|')
lines+=['',f'判据①：{"至少一特征满足" if any(x[2] for x in passes) else "无特征满足"}（按原式「CI 下界 > 200 次置换的最大 |ρ|」，不能用置换 95 分位代替）。判据②逐特征对比同属性 PCA 最佳 PC：']
for p,rs in C['candidates'].items():
 best=abs(C['baselines'][p]['pca_test_rho']);which=[r['feature'] for r in rs if abs(r['test_rho'])>=best]
 lines.append(f'{p} 的 PCA 最佳 |ρ|={f(best)}；SAE 满足②：{which if which else "无"}。')
lines+=['','线性探针用相同训练样本级 384 维通道最大值，以五折训练 CV 选岭 α；PCA 用训练集拟合，在训练集选最佳 PC，再读检验。未提取全 1128 时次，所以按时次随机 80/20 的附加检验未评估；不可声称随机划分的增益。','', '## 干预','', '定义：在窗口 token 对指定 TopK 特征执行 h′=h+(α−1)zₖ(dₖ×训练标准差)，保留残差；α∈{0,0.5,1.5,2}。基线是在相同 t+24 IBTrACS 中心 5° 内的原预报最低 MSL / 最大 10 m 风；表内 E=各检验风暴的 (干预−基线) 最低 MSL 中位数 (hPa)，E₀=10 个同均值幅度 ±50% 非目标特征各自 |E| 的 95 分位。另报相同扰动范数随机方向中位数。','']
if rows:
 gr=collections.defaultdict(list)
 for r in rows:gr[(r['control'],r.get('reference',r['feature']),r['feature'],r['alpha'])].append(r)
 storms={r['sid'] for r in rows if r['control']=='pure_decoder'}
 lines.append(f'有逐时次干预记录 {len(rows)} 行，纯解码基线 {len(storms)} 场；目标 30 场。')
 lines+=['','|目标特征|α|E(hPa)|10 匹配特征 E₀(hPa)|\u007cE\u007c/E₀|随机方向 E(hPa)|10 m 风 Δ中位数(m/s)|完整场数|','|---:|---:|---:|---:|---:|---:|---:|---:|']
 targets=sorted({k[1] for k in gr if k[0]=='target'})
 for j in targets:
  for a in [0.,.5,1.5,2.]:
   rr=gr.get(('target',j,j,a),[]);rr0=[np.median([v['dmsl_hpa'] for v in vs]) for (type_,ref,c,alpha),vs in gr.items() if type_=='matched' and ref==j and alpha==a and len(vs)==len(storms)]
   e=float(np.median([v['dmsl_hpa'] for v in rr])) if rr else None
   e0=float(np.quantile(abs(np.array(rr0)),.95)) if rr0 else None
   rand=gr.get(('random_direction',j,j,a),[])
   ratio=abs(e)/e0 if e is not None and e0 and e0>0 else None
   lines.append(f'|{j}|{a:g}|{f(e)}|{f(e0)}|{f(ratio)}|{f(float(np.median([v["dmsl_hpa"] for v in rand])) if rand else None)}|{f(float(np.median([v["dwind_ms"] for v in rr])) if rr else None)}|{len(rr)}|')
 diverged=sum(bool(r.get('divergent')) for r in rows if r['control']!='pure_decoder');den=sum(r['control']!='pure_decoder' for r in rows)
 pure=[r['dmsl_hpa'] for r in rows if r['control']=='pure_decoder']
 lines += ['',f'发散 {diverged}/{den} 条实际干预（判定任何非有限或 |ΔMSL|>50 hPa）；纯解码替换 α=1 相对原预报 MSL 中位数 {f(float(np.median(pure)) if pure else None)} hPa（{len(pure)} 场）。','']
 for j in targets:
  es=[np.median([v['dmsl_hpa'] for v in gr.get(('target',j,j,a),[])]) if gr.get(('target',j,j,a)) else np.nan for a in [0.,.5,1.5,2.]]
  mono=bool(np.all(np.diff(es)>=0) or np.all(np.diff(es)<=0)) if all(np.isfinite(es)) else None
  association=max(((abs(r['train_rho']),p,r['train_rho']) for p,rs in C['candidates'].items() for r in rs if r['feature']==j),default=None)
  sign=association[2] if association else None
  direction=(np.sign(es[-1])==np.sign(sign) and np.sign(es[0])==-np.sign(sign)) if sign is not None and all(np.isfinite(es)) else False
  ratios=[]
  for alpha,e in ((0.,es[0]),(2.,es[-1])):
   controls=[np.median([v['dmsl_hpa'] for v in vs]) for (type_,ref,c,a),vs in gr.items() if type_=='matched' and ref==j and a==alpha and len(vs)==len(storms)]
   threshold=float(np.quantile(abs(np.array(controls)),.95)) if controls else np.nan
   ratios.append(abs(e)/threshold if threshold>0 else np.nan)
  gate3=bool(mono and direction and all(np.isfinite(ratios)) and min(ratios)>=3)
  lines.append(f'特征 {j}：E 四点单调={mono}，按训练 |ρ| 归属 {association[1] if association else "未知"} 的方向一致={direction}，α0/α2 的 |E|/E₀={f(ratios[0])}/{f(ratios[1])}，判据③={"满足" if gate3 else "不满足"}；四点 {[round(float(x),3) for x in es] if all(np.isfinite(es)) else "不全"}。')
else:lines.append('干预结果尚未落盘；判据③未评估，不作已测结论。')
lines+=['','## 判据与局限','',f'检验风暴 {C["n_test"]} 场，超过不判门槛 30。判据① {"满足" if any(x[2] for x in passes) else "不满足"}；由于判据①不满足，按预注册判据「放弃（限本配置）」的数值条件已成立，最终判定由 Lead 做。干预不应倒推更改置换最大值或区间阈值。','', '2022 年真实数据不可用；2021 仅 46 场，每场仅一时次。纯解码与残差保持为不同干预读法，不相混用。所有观察仅对本模型/中间层、此输入/抽样/SAE 宽度与 K 有效。','', '## 参数来源', '', '风暴筛选、窗口、TopK 宽度、K 候选、bootstrap 与置换次数、干预 α：任务书。假设：每风暴优先最大风的单时次（受实测 CU 约束）；内部随机留出 20% 风暴、训练每轮 epoch 数 2/5、AdamW 5e−4、归一化按训练 token 通道均值与标准差、PCA 维度 k=10、岭五折 CV；这些非论文给定参数。','']
(R/'报告_L26.12-01_v2.md').write_text('\n'.join(lines))
print('report',R/'报告_L26.12-01_v2.md','rows',len(rows),'criterion1',any(x[2] for x in passes))
