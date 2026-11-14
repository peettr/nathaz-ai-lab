import csv, json, statistics
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path(__file__).resolve().parent
rows=list(csv.DictReader((p/'run2/station_rows_v1.csv').open()))
s=json.loads((p/'run2/summary_v1.json').read_text())
lines=['# B1+B4 最佳路径链 v1：预注册复测','',
'冻结文件：`PREREG_v1.md`（10-14 15:19 EDT；在本轮 v1 与观测对照前）；软件 CLIMADA 6.1.0 H08 commit `bb9595944fcf673152ea53e61efbafeb0b1e4406`，地表定向粗糙度乘子及 2min/5s 时距假设均按预注册。不是 Vickery slab；CLIMADA 原生 H08 为 10m 1min 场，矢量加入平移非对称，源码 `trop_cyclone_windfields.py` 第 1131–1257 行。','',
'按站点 e=峰值预测/峰值观测−1，median(|e|) / median(e)。输入 NHC HURDAT2+ATCF b-deck、IEM/NCEI ASOS 1min、Natural Earth 10m land polygon；图表均标明来源。',
'',f"持续风（约 2min sknt，n={s['s']['n']}）：中位绝对误差 {100*s['s']['median_abs_error']:.2f}%；中位偏差 {100*s['s']['median_bias']:+.2f}%。±20% 偏差闸：通过；但绝对误差 21.02% >20%，不应误称总体误差全在 ±20%。",
f"5s 阵风（gust_sknt，n={s['g']['n']}）：中位绝对误差 {100*s['g']['median_abs_error']:.2f}%；中位偏差 {100*s['g']['median_bias']:+.2f}%。",
f"候选 {s['stations']} 站；截尾 {s['truncated']} 站；物理 QC 剔除 {s['qc']} 站；请求失败 {s['request_error']} 站；IDA 和 IDALIA 无合格站。全部 12 个事件均已尝试。",'',
'| 事件 | 候选/合格 | 截尾 | 持续风中位绝对误差 / 偏差 | 阵风中位绝对误差 / 偏差 |','|---|---:|---:|---:|---:|']
for name,d in s['by_event'].items():
 rr=[r for r in rows if r['event']==name]
 def fmt(k):
  x=[float(r[k]) for r in rr if r[k]]
  return f'{statistics.median(abs(v) for v in x)*100:.1f}% / {statistics.median(x)*100:+.1f}%' if x else '不可算'
 lines.append(f"| {name} | {d['candidate']}/{d['eligible']} | {d['truncated']} | {fmt('err_s')} | {fmt('err_g')} |")
lines+=['','## 执行与边界',
'第一次执行把任何一个 15 min 节点缺少 RMW/POCI 的事件整体剔除，导致 Beryl 和 Francine 未入；错误运行结果原样保留在 v1 根目录的 `summary_v1.json` 和逐事件表。代码随后仅修正“缺失节点剔除，而非整事件剔除”的预注册实现错误，在 `run2/` 新目录重算，未改模型、常数或站点规则。以上正式 v1 数字来自 `run2/summary_v1.json`；原输出绝不覆盖。','IEM 原始分钟档的严重天气断报并非随机；90% 模型峰窗规则剔除了 34/67 站，Milton 只剩 1 站。自然地表仅陆/海、未解析机场不同方向具体地类与地形；500m 对数层参考高度、1min→2min 因子和 1min→5s 因子均为冻结的假设，非作者给定通用换算。IEM sknt 是约 2min 代理，不是严格 1min 配对；阵风因子虽有 Powell 等 2005 PDF 2–3、5–6 页的定义/暴露依据，其数值为假设。故“闸通过”仅限预注册的代理比较，不能说物理风场已普适验证。','不同站的误差方向和事件样本强烈不均衡；29 个站来自 10 个事件，非 12 个事件每个都有质量合格观测。','',
'AIWP 切片单列 `aiwp_slice_measurement.md`；Colab CPU 会话已停止。B1 后续 (b)(c) 应由 Lead 判断是否接受上述 2min 代理/时距假设作为主闸再推进。',
'','文献：Vickery 等 2009 PDF 第 12/15/22 页粗糙度示例（卡 `WTPZS77N_vickery_2009_engineering.md` 第 12 行）；Powell 等 2005 PDF 第 2–3、5–6 页（候选卡 `ZR7S3SEJ.md` 第 62、88–92 行）；Krayer–Marshall 1992 PDF 第 2–4 页（候选卡 `2KXRIJJB.md` 第 60、74–76 行）。卡片的独立审查未完成，暂按候选依据引用。']
(p/'chain_a_v1_results.md').write_text('\n'.join(lines)+'\n')
fig,ax=plt.subplots(figsize=(10,5.5))
y=[];labels=[]
for name in s['by_event']:
 rr=[r for r in rows if r['event']==name and r['err_s']]
 for r in rr:y.append(float(r['err_s'])*100);labels.append(name)
for i,name in enumerate(s['by_event']):
 vals=[float(r['err_s'])*100 for r in rows if r['event']==name and r['err_s']]
 if vals:ax.scatter([i]*len(vals),vals,s=18,color='#1769aa',alpha=.7);ax.plot([i-.22,i+.22],[statistics.median(vals)]*2,color='black',lw=2)
ax.axhspan(-20,20,color='#89c780',alpha=.25,label='Frozen bias window ±20%');ax.axhline(0,color='gray',lw=.8)
ax.set_xticks(range(len(s['by_event'])),list(s['by_event']),rotation=45,ha='right');ax.set_ylabel('Peak 2-min proxy: predicted / observed − 1 (%)');ax.legend(loc='upper right')
ax.set_title('B1+B4 best-track chain v1 (eligible station dots, event medians black)')
fig.text(.02,.01,'Sources: NHC HURDAT2 + ATCF b-decks; IEM/NCEI ASOS 1-min; Natural Earth 10m land; CLIMADA v6.1.0.',fontsize=8)
fig.tight_layout(rect=[0,.04,1,1]);fig.savefig(p/'chain_a_v1_ratio.png',dpi=145);plt.close(fig)
print('report plot created',len(y),s['stations'])
