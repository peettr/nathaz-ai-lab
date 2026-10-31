"""Summarize append-only AIWP cases with per-parameter preregistered gate."""
import csv,json,collections,math,pathlib,numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=pathlib.Path(__file__).parent
K=['MUCAPE','MLCAPE','DCAPE','shear06','shear01']; LEADS=[12,24,48,72,120]; MODELS=['PANG','GRAP']
events=list(csv.DictReader((R/'events_M.csv').open())); raw=[]
for path in [R/'raw_cases.jsonl']+sorted(R.glob('raw_shard_*.jsonl')):
 if path.exists():raw.extend(map(json.loads,path.read_text().splitlines()))
latest={}
for r in raw:latest[(r['event_id'],r['model'],r['lead_h'])]=r
stats=[];details=[]
for model in MODELS:
 for lead in LEADS:
  for k in K:
   pair=[];missing=[]
   for e in events:
    r=latest.get((e['event_id'],model,lead))
    if not r or r['status']!='ok':missing.append(e['event_id']+':'+(r.get('error','')[:65] if r else 'no case'));continue
    vals=[r[x][k] for x in ['forecast','reference','baseline']]
    if any(v is None or not math.isfinite(v) for v in vals):missing.append(e['event_id']+':invalid profile');continue
    a,b=abs(vals[0]-vals[1]),abs(vals[2]-vals[1]);pair.append((a,b))
    details.append(dict(event_id=e['event_id'],model=model,lead_h=lead,parameter=k,forecast=vals[0],era5=vals[1],persistence=vals[2],ai_ae=a,persistence_ae=b,ai_better=a<b))
   a=np.array(pair);n=len(pair);ma=float(np.median(a[:,0])) if n else None;mb=float(np.median(a[:,1])) if n else None;better=int(np.sum(a[:,0]<a[:,1])) if n else 0
   gate=n>=30 and ma<=.8*mb and better/n>=2/3 if n else False
   stats.append(dict(model=model,lead_h=lead,parameter=k,n=n,median_ai_ae=ma,median_p_ae=mb,median_ratio=ma/mb if n and mb else None,ai_better=better,better_fraction=better/n if n else None,pass_gate=gate,missing=missing))
with (R/'parameter_event_errors.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=details[0].keys());w.writeheader();w.writerows(details)
(R/'summary.json').write_text(json.dumps(stats,indent=2,ensure_ascii=False))
units={'MUCAPE':'J/kg','MLCAPE':'J/kg','DCAPE':'J/kg','shear06':'m/s','shear01':'m/s'}
fig,axs=plt.subplots(5,2,figsize=(11,15),layout='constrained')
for i,k in enumerate(K):
 for j,m in enumerate(MODELS):
  ax=axs[i,j];rr=[x for x in stats if x['model']==m and x['parameter']==k]
  ax.plot([x['lead_h'] for x in rr],[x['median_ai_ae'] for x in rr],'-o',label=m+' AIWP GFS')
  ax.plot([x['lead_h'] for x in rr],[x['median_p_ae'] for x in rr],'--s',label='ERA5 persistence')
  ax.set(xlabel='Lead (h)',ylabel=f'Median absolute error ({units[k]})',title=f'{m} {k}')
  ax.legend(fontsize=8)
fig.text(.5,.002,'Sources: NOAA-CIRA AWS AIWP GFS reforecasts; Google ARCO-ERA5 13-level reference and persistence; NOAA NCEI Storm Events ASOS.',ha='center',fontsize=8)
fig.savefig(R/'errors_by_parameter_sources.png',dpi=150)
lines=['# AWS AIWP 强对流大风环境多事件回算','',f'事件清单 {len(events)} 个不同 UTC 日；完成可用参数事件值 {len(details)} 条；原始案例记录 {len(raw)} 行（同一键取最后一行）。','', '预设闸门：逐参数、逐模型、逐时效，事件中位绝对误差 AI ≤ 0.8 × 持续性，且 AI 逐事件优于持续性 ≥ 2/3；完整性另要求该格不少于 30 个事件，未达时不以缺失子集放行。对照为同站中心 3×3 的区域最大值。','','|模型|提前 h|参数|有效/40|AI 中位 AE|持续性中位 AE|比值|逐事件优于|达标|','|---|---:|---|---:|---:|---:|---:|---:|---|']
for r in stats:
 def s(x):return '—' if x is None else f'{x:.2f}'
 lines.append(f"|{r['model']}|{r['lead_h']}|{r['parameter']}|{r['n']}/40|{s(r['median_ai_ae'])}|{s(r['median_p_ae'])}|{s(r['median_ratio'])}|{r['ai_better']}/{r['n']}|{'是' if r['pass_gate'] else '否/证据不足'}|")
lines+=['','## 13 层与 37 层参照差异']
for k in K:
 diffs=[]
 for e in events:
  r=next((latest.get((e['event_id'],m,l)) for m in MODELS for l in LEADS if latest.get((e['event_id'],m,l),{}).get('status')=='ok'),None)
  if r and r['reference'][k] is not None and r['reference_37'][k] is not None:diffs.append(abs(r['reference'][k]-r['reference_37'][k]))
 lines.append(f"- {k}: 有效 {len(diffs)}/{len(events)}，区域最大值的13对37层中位绝对差 {np.median(diffs):.2f} {units[k]}。" if diffs else f'- {k}: 尚无可比数据。')
lines+=['','说明：单位 CAPE/DCAPE J/kg、风切 m/s；未混合单位。0.25° 网格，站点所在格±一个格点是未给区域范围时的事前实现假设。事件时刻取最近 00/12 UTC 整点，可能偏离风峰至 6 h，只检验环境不检验阵风。', 'ERA5 同一 13 等压层作主参照；37 层附随每案例 reference_37 字段；持续性为验证时刻前 24·ceil(L/24) h 的 ERA5。气块定义沿用三事件试验：MetPy mixed_layer_cape_cin 默认 100 hPa、most_unstable_cape_cin 默认 300 hPa，downdraft_cape 默认中层；地面 10 m 风线性插值至 1/6 km AGL。地形以下层由 ERA5 地表位势遮罩，FCN v2-small 归档实际缺完整热力/风层而未参与五参数。','完整性：每个单元的缺失事件可在 summary.json 查询，原始报错保留 raw_cases.jsonl；缺失不以 0 代入。','数据来源：Radford et al. (2025), BAMS DOI 10.1175/BAMS-D-24-0057.1；NOAA-CIRA AWS https://registry.opendata.aws/aiwp/；ERA5 Hersbach et al. (2020) DOI 10.1002/qj.3803，经 Google ARCO；NOAA NCEI Storm Events 年度 CSV。']
(R/'results.md').write_text('\n'.join(lines)+'\n')
print('CASES',len(raw),'DETAILS',len(details),'GATES',sum(x['pass_gate'] for x in stats),'MIN_N',min(x['n'] for x in stats))
