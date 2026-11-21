from pathlib import Path
import json,datetime,hashlib,re
r=Path(__file__).parent;d=json.loads((r/'metrics_caseA_r216_0b.json').read_text());man=json.loads((r/'final/out/manifest.json').read_text());e=json.loads((r/'final/out/evidence_r9_dx4.json').read_text())
def f(x):return f'{x:.3f}' if x is not None else 'NA'
rows=[]
for case in ('r9_dx4','r9_dx10'):
 x=d[case]
 for group in ('z8','z80','vertical'):
  for shift in ('no_shift','selected'):
   a=x['primary'][group][shift];rows.append('|'.join([case,{'z8':'4 m','z80':'40 m','vertical':'竖剖面'}[group],shift,str(a['n']),str(a['n_tke'])]+[f(a[k]) for k in ('FAC2','q_abs025','q_rel025','r','NRMSE_range','NRMSE_mean','TKE_FAC2','TKE_r','mean_ratio')]+[str(a['mixed_solid'])]))
# Capture stop timestamp from terminal return (known to second), creation timestamp from keepalive.
start=datetime.datetime(2026,11,2,7,40,13);end=datetime.datetime(2026,11,2,7,54,51);cost=(end-start).total_seconds()*5.4/3600
base='''# R21.6-0b Case A 4 m/10 m 第九轮网格试验（11-02 美东）

偏离 Liang Hu 要求：本次 A100 会话按创建至停止计约 {cost:.3f} CU，超过 1 CU 总上限和 0.9 CU 停报线；原因是求解完成后 10 m VTK spacing 并非 10.0 m，提取器断言失败，修复与拉取验证耗时，加之会话启动后上传/构建和 CLI/本地 I/O 时间未纳入远端 0.9 CU 守卫。已停止自己创建的会话；需 Liang Hu 确认这一预算偏离。未启动第八轮，也没有另开会话或重跑求解器。

本线使用公开 LUW HEAD `dd438c1c68664980a92460e4778f18f36be3f47c`；第九轮入口 `TI=0.1468030617, L=100 m, inflow_only, TARGET_INFLOW`。只改 `cell_size` 与为保持同一物理时长必须同步换算的步数/stride；10 m 的格数取整和 VTK 实际 spacing 是附带复合改动。源码 `setup.cpp:3547–3562,3854–3855,4269` 中 dt=cell_m×0.1/si_ref_u，随 cell_m 成正比。4 m：16000 步、末 11000 步每 20 步，共 550；10 m：6400 步、末 4400 步每 8 步，共 550；相对原 2 m 的 32000/末22000/stride40，物理平均窗约 647 s。200 m sponge 维持物理厚度；VK L 维持 100 m（继承假设）。10 m 实际网格 109×70×38，VTK spacing=10.057143 m；4 m 为272×176×96、spacing=4 m。物理域配置、STL、profile 不变。4/40 m 是官方水平面；8/80 m 只作非同高度备查。4 m 高度低于 10 m 网格首格尺度，但本次 VTK 垂直原点 -20 m，提取器仅做域边界钳位，不是地面首流体格修正；因此 10 m 的近地指标仅描述该粗格采样，不能当充分解析的近地验证。

各 dx 的掩膜按 z=32 m 建筑 32×32 m 截面 IoU（非 MAE）选偏移：4 m 选 (4,4,0) m，IoU={iou4}; 10 m 选 (10.057143,10.057143,0) m，IoU={iou10}。输出同时保留 no_shift。`mixed_solid` 指插值 8 角中至少一个固体的点数，不删这些点。速度是平均三分量的模/U_H；k 仅解析部分/U_H²。q_abs025、q_rel025 和两种 NRMSE 的定义属先前假设，不声称论文同口径。TKE FAC2/r 仅保留 |k_obs/U_H²|>0.05 的点。

|场|高度/组|偏移|n|n_tke|FAC2|q_abs025|q_rel025|r|NRMSE_range|NRMSE_mean|TKE_FAC2|TKE_r|mean_ratio|mixed_solid|
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{table}

诊断 8 m、80 m 每组 60 点、no_shift/selected 的同定义数字在 `metrics_caseA_r216_0b.json` → diagnostic，逐点坐标和值在 `final/out/samples_r9_dx4.json` 与 `final/out/samples_r9_dx10.json` → diagnostic；原交接旧 `metrics_caseA.json` 的 z8/z80 实为 4/40 m，本次不混用。诊断组若按官方 4/40 m 观测列算指标，仅供采样位置敏感性参考，绝非同高度风洞检验。

运行有效性：4 m solver exit=0，达到16000/16000 步，550个样本，墙钟 {wall4:.2f}s；10 m solver exit=0，达到6400/6400 步，550个样本，墙钟12.08s。两日志均有末步和 Task finished；日志没有 NaN/nonfinite/diverg 词，逐点所有三分量和 k 均有限（不等于对整场逐格扫描）。4 m 平均 VTK 110297487 B，10 m 平均 VTK 6958963 B，保留在停止前的远端瞬态 VM，未取回大文件；下载的是逐点样本与日志。4 m 样本269367 B，日志115477 B；10 m 样本269360 B，日志28457 B；各写出时间/sha256见 `final/out/manifest.json`（文件里的 mtime 为 Unix epoch，可换算美东）。10 m 求解完成后首次提取失败于 `assert abs(dx-spacing)<.01`，因为真实 VTK spacing=10.057143；未重算求解，只对同一平均 VTK 用 0.1 m 容差重新提取成功，`final/failed` 保留错误证据。实验卡的 Colab 副本与本地提交前版本一致；本地卡事后补记实际 spacing 和诊断。

远端 `deliverables.zip` SHA256 `d1d64a19f87717c23e28ef7f29ddef4d719085420014a9c9020d4efde3fa7526`，本地同哈希，解包前逐文件按远端 manifest 核验 10 个文件的大小及 sha256；原始主表逐点样本两份均为60/60/66点。会话创建 11-02 07:40:13 EST，停止并由账户 `sessions` 确认不再列出 11-02 07:54:51 EST；按 5.4 CU/h 的区间估算 {cost:.3f} CU，不以共享账户余额差作为本单耗费。keepalive 首轮 `exec_ok=1`、后续=2；会话停止后 user unit inactive。第八轮未运行：远端报错时已超过0.7 CU门槛，故不再启动。

本稿只报告本事件各配置各指标；粗格近地混固与掩膜 IoU 的限制不作物理误差归因，也不判优劣。未触及 T1c4/T2。
'''
text=base.format(cost=cost,iou4=f(d['r9_dx4']['selected_shift']['iou']),iou10=f(d['r9_dx10']['selected_shift']['iou']),table='\n'.join('|'+a+'|' for a in rows),wall4=e['wall_s'])
(r/'RUN_caseA_r216_0b.md').write_text(text)
print('report',r/'RUN_caseA_r216_0b.md','rows',len(rows),'cost',cost)
