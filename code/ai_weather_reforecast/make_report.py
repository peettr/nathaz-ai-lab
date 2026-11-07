"""Build concise Chinese report from downloaded Colab metrics, no manual transcription."""
import json,statistics,collections,datetime,math,pathlib
root=pathlib.Path('./22_Lab/06_Logs/ai_weather_reforecast')
m=json.loads((root/'metrics.json').read_text()); times=json.loads((root/'timings.json').read_text())
assert len(m['cases'])==20 and all('judge' in x for x in m['cases'])
assert all(x['summary']['_error_count']==0 for x in m['cases'])
rows=[]
for x in m['cases']:
 j=x['judge']; fmt=lambda v:'是' if v else '否'
 rows.append(f"| {x['model']} | {x['event']} | {x['lead_h']} | {fmt(j['c1'])} | {fmt(j['c2'])} | {fmt(j['c3'])} ({j['distance_km']:.1f} km) | {fmt(j['pass_all'])} | {j['mae_ai']:.1f} / {j['mae_p']:.1f} |")
def line(e,keys):
 a=m['reference'][e];b=m['supplementary_37'][e]
 return '\n'.join(f"| {key} | {a[key]['max']:.2f} | {b[key]['max']:.2f} | {b[key]['max']-a[key]['max']:+.2f} |" for key in keys)
def maxlead(model,event):
 q=[x['lead_h'] for x in m['cases'] if x['model']==model and x['event']==event and x['judge']['pass_all']]
 return f'{max(q)} h' if q else '无（所测提前量均不满足）'
dedup={}
for x in times:
 if x['model']=='FuXi' and x['event']=='E1' and x['lead_h']==24 and 'v2' in x['output']:continue
 dedup[(x['model'],x['event'],x['lead_h'])]=x
assert len(dedup)==20
median={s:statistics.median(x['seconds'] for x in dedup.values() if x['model']==s) for s in ['Pangu6','FuXi']}
supp=m['supplementary_00utc']
s='''# AI 天气模型回算两个下击暴流环境：最小试验结果（2026-10-13）

性质：n=2 的回顾性、ERA5 初始化确定性全球模型环境筛查；绝非下击暴流发生时间、阵风或概率的预报验证。空间分辨率 0.25°。原定三个闸门全部保留，没有改阈值。

## 最大满足提前量

'''
for model in ['Pangu6','FuXi']:
 for event in ['E1','E2']:
  s+=f'- {model} × {event}：{maxlead(model,event)}。\n'
s+='''
E1 为 Wister 2018-08-10 18 UTC，E2 为 Akron 2020-06-09 06 UTC。Pangu 在 E1 12 h、E2 12 h 满足；FuXi 在 E1 12/24 h 满足，E2 所有测试提前量均不满足。最长可用时效是离散测试集中的最大值，不能外推其间时刻。

## 预定判据表

第 1 项：E1 的 MLCAPE/DCAPE/0–6 km 切变分别 ≤25%/≤25%/5 m s⁻¹；E2 的 MUCAPE/0–6 km 切变/逆温分别 ≤25%/5 m s⁻¹/2 K。第 2 项：上述三个区域最大值对 13 层 ERA5 的绝对误差作简单算术平均，AI ≤0.70×同起报日变化对齐 ERA5 持续性基线 P 的误差。该原文口径将 J kg⁻¹、m s⁻¹、K 混合平均，物理单位不一致；下表仅按预定字面算法执行，不将其解释为无量纲综合 skill。第 3 项：模型区域 MUCAPE 最大格点距事件点 ≤150 km。若并列最大，取数组遍历的首格点；零 CAPE 的个案其位置无物理意义，但仍依固定代码裁决。均为区域最大值，不以面积平均替代；全部区域均值在 metrics.json。

| 模型 | 事件 | 提前 h | ①参数 | ②较 P 好≥30% | ③定位≤150 km | 全部 | 平均绝对误差 AI/P（混合单位） |
|---|---|---:|---|---|---|---|---:|
'''
s+='\n'.join(rows)+'\n'
s+='''
持续性定义 P(t,L)=ERA5(t−24·ceil(L/24) h)。区域 E1 34.5–35.5°N、95.2–94.2°W，E2 39.5–41.5°N、104.5–101.5°W；实际网格采用区域内精确 0.25° 坐标（E1 经度 −95.0…−94.25°），未作任意边缘插值。格点距离为球面大圆距离。

## 13 层与 37 层参照的差别

同一验证时刻、同一 0.25° 水平网格，37 层只作附注，不用于裁决；下表为区域最大值（37 层减 13 层）。近地地下等压面用 ERA5 固定地形位势遮罩；最底有效气压面不等于地表。

| E1 指标 | ERA5 13 层 | ERA5 37 层 | 差值 |
|---|---:|---:|---:|
'''+line('E1',['MLCAPE','MUCAPE','DCAPE','shear06'])+'\n\n| E2 指标 | ERA5 13 层 | ERA5 37 层 | 差值 |\n|---|---:|---:|---:|\n'+line('E2',['MUCAPE','shear06','inversion_K'])
s+=f'''

E1 13 层的区域最大 MLCAPE 为 {m['reference']['E1']['MLCAPE']['max']:.1f} J kg⁻¹，37 层为 {m['supplementary_37']['E1']['MLCAPE']['max']:.1f} J kg⁻¹；层数差异不可忽略。E2 的 13 层最大逆温升温 {m['reference']['E2']['inversion_K']['max']:.2f} K，上端高度约 {m['reference']['E2']['inversion_height_m']['max']:.0f} m AGL；37 层最大值 {m['supplementary_37']['E2']['inversion_K']['max']:.2f} K。这个定义是 0–3 km 内相邻高度层最大正温差，不是追踪 Akron 事件约 1.3 km AGL 那个特定逆温层，因此 E2 对高架对流的判读尤其脆弱。E1 次日 00 UTC 13 层 ERA5 的 MLCAPE/MUCAPE/DCAPE/0–6 km 切变区域最大值为 {supp['MLCAPE']['max']:.1f}/{supp['MUCAPE']['max']:.1f}/{supp['DCAPE']['max']:.1f} J kg⁻¹ 与 {supp['shear06']['max']:.1f} m s⁻¹，纯作时次参考，不纳入判据。

## 定义与局限

MetPy 1.7.1：MLCAPE 采用 mixed_layer_cape_cin 默认底部 100 hPa 混合层；MUCAPE 采用 most_unstable_cape_cin 默认底部 300 hPa；DCAPE 采用 downdraft_cape 的 700–500 hPa 最小 θe 起始层；0–1/0–6 km 切变采用 10m 地面风与 MetPy bulk_shear 高度插值，递减率为 2m 到 3 km 的温差/3 km；可降水量采用 MetPy precipitable_water，在最低有效等压面以上积分。露点由 q 推算（FuXi 为 RH 推算），未把地表湿度强行填成等压层；近地湿度和 DCAPE 等指数因此有截断偏差。逆温用 2m 温度和地面以上有效等压层的最大相邻正温差，上端高度随一起输出。参数均逐格计算、区域内最大与 cosφ 加权平均，详见 metrics.json 的 n_valid 与错误计数。两模型都是基于 ERA5 再分析初值的后验 hindcast，不能证明实时业务中 ERA5 的获取时延可行。E2 峰位靠近 150 km 阈值（Pangu 12 h 为 {next(x for x in m['cases'] if x['event']=='E2' and x['model']=='Pangu6' and x['lead_h']==12)['judge']['distance_km']:.1f} km），边界/地形/高度定义改变可能翻转。

FuXi 输出 RH 而 Google ARCO Earth2Studio 词典不直接提供 r 层变量：由同层 ERA5 q、T、p 用水面饱和水汽压转换成 RH、限幅 0.1–100%，再喂 FuXi；这一数据适配不是重新训练，对冰相及近零水汽情况有近似误差。Pangu 用原生 ARCO q。没有使用 GraphCast operational；其 2016–2021 HRES 微调跨越两事件，标准 ERA5 37 层版在 Earth2Studio 当时没有同样的即用封装；改用同为 0.25°/13 层的 FuXi。

## 训练期与权重使用条件

Pangu-Weather：原模型训练 ERA5 1979–2017，2018 与 2020 留出（WeatherBench 2 §3.9，https://arxiv.org/html/2308.15560v1；原仓库 https://github.com/198808xc/Pangu-Weather）。本次 Earth2Studio `Pangu6` 经 NickGeneva/earth_ai 镜像取得 ONNX 文件，未独立按哈希比对与论文原始权重，故“此镜像权重与论文完全同一版本”未核。原仓库 README §License：trained parameters 为 CC BY-NC-SA 4.0、禁止商业使用，https://raw.githubusercontent.com/198808xc/Pangu-Weather/main/README.md 。

FuXi：论文说明训练 1979–2015、验证 2016–2017、2018 测试，事件日期不在所述训练/验证期（https://arxiv.org/pdf/2306.12873；作者仓库 https://github.com/tpys/FuXi）。本次使用 Earth2Studio FuXi wrapper 与 NickGeneva/earth_ai 镜像 short/medium/long 权重；镜像自身的 README 给出“CC BY-NC-SA 4.0”（https://huggingface.co/NickGeneva/earth_ai/resolve/main/fuxi/README.md），因此按非商用处理；与原论文原始权重逐文件哈希、镜像具体训练日期尚未独立核实，不能把论文数据拆分当作镜像权重逐字节证明。原 FuXi 仓库 README 没有单列权重许可文本，商用授权不得据此推断。Earth2Studio 代码自身 Apache-2.0，与权重许可不同。GraphCast 原始权重 CC BY-NC-SA 4.0（https://github.com/google-deepmind/graphcast）；本次未运行。

## 成本、文件与复现

Colab A100-SXM4-40GB，一次会话 `lab-ai-weather-1013`，冷启动 `new` 返回 READY（初次 Colab 服务 503，第二次成功；未单独计时，不能报精确冷启动秒数）。2 模型 × 2 事件 × 5 提前量，共 20 个唯一起报组合；由于 FuXi 原 ARCO 缺 RH、以及连续重新实例化 ONNX 导致显存不足，留下失败原始日志与一个额外成功的 FuXi E1 24h 重复（不参与指标）；对模型正式表只取 20 个唯一组合。成功运行的从模型加载到区域写出的耗时中位数 Pangu {median['Pangu6']:.1f} s、FuXi {median['FuXi']:.1f} s（单次含约 12–120h 不同预报、ARCO 取数/ONNX 装载，非纯 GPU 前向时间）。本会话创建前账户余额 1507.42 CU，停止后 1497.70 CU；账户净变动 9.72 CU，但开头曾有另两项 A100 同时运行，不可归因本任务；本任务 A100 计费率 5.30 CU/h，单任务持续不足约一小时，按此上限估算 <5.30 CU，低于 20 CU 预算。已执行 `colab stop`，随后 `colab sessions` 返回 `No active sessions found on server`，usage 返回 0.00/hr、0 活动分配。

复现：`forecast.py`（需在 Colab 用 `runpy` 给 model/event/lead_h 传参），`extract_truth.py`、`metrics.py`；环境 earth2studio 0.19.0、MetPy 1.7.1、torch 2.11.0+cu130、onnxruntime-gpu、zarr、xarray。比较中仅取远端 ARCO 原始 Zarr 区域小切片，本地没有模型权重/全球 ERA5；会话停止后大权重与远端 Zarr 预测区域暂存均销毁。可复核成品：`metrics.json`、`timings.json`、`errors.png`；`raw_forecast.log`、`raw_fuxi_smoke*.log`、`raw_fuxi_resume.log`、`raw_fuxi_E*_v3.log`、`raw_truth*.log`、`raw_metrics*.log` 为原始日志（失败也保留，不误写为有效结果）。

一行判读：有探索价值——Wister 的 12–24 h、Akron 的 12 h 有模型在预先固定的三个闸门同时过关；仅 n=2、0.25° 背景场，且 13 层缺低空结构、FuXi 权重来源还需逐权重核验，不能推到下击暴流本身或一般化时效。
'''
p=root/'results.md';assert not p.exists();p.write_text(s);print(p,len(s),len(rows),len(dedup),median)
