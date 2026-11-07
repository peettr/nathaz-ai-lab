"""Programmatic 27-init RMSE comparison; reads existing files, creates new output only."""
from pathlib import Path
import re, numpy as np
b=Path(__file__).resolve().parents[1]
old=np.load(b/'colab02/final/rmse_surface_00z_smoke10.npy')
new=np.load(b/'colab06/final/rmse_surface_00z_smoke17.npy')
assert old.shape==new.shape==(4,73)
log=(b/'colab06/final/surface.log').read_text()
assert 'Evaluation Complete [00Z Only, Surface Variables] (17 batches' in log
assert 'Init: 2024/04/11/00' in log and 'Init: 2024/04/21/00' in log
ref={'Z300':11.2359,'Z500':8.1793,'Z700':6.7832,'Z850':7.2936,'Z925':8.5356,'T300':.7304,'T500':.6898,'T700':.8177,'T850':1.2171,'T925':1.3419,'MSLP':114.8514,'U10':1.8043,'V10':1.8601,'T2m':1.5562}
air={'Z300':11.2465,'Z500':8.175,'Z700':6.7734,'Z850':7.2885,'Z925':8.5348,'T300':.7306,'T500':.6899,'T700':.8181,'T850':1.2166,'T925':1.3412}
assert len(air)==10 and len(ref)==14
combined=np.sqrt((10*old.astype('float64')**2+17*new.astype('float64')**2)/27)
ours=air|dict(zip(('MSLP','U10','V10','T2m'),combined[:,1:].mean(axis=1).tolist()))
within=sum(abs(ours[k]-r)/r<=.10 for k,r in ref.items())
over=sum(abs(ours[k]-r)/r>.25 for k,r in ref.items())
lines=['# L26.4 ①官方西部同一 27 起报对照','', '数据来源：Zhang et al. (2026) AERO-ODE commit 99516ae9cf 官方 AIR/Surface run.log（2024-04-01…27 每日 00Z）；作者 HF 案例 ERA5/HRRR。我们的 AIR 为 CRC A10 作业 1603191（复合显存管理改动，实验卡 EXPERIMENT_CARD_run04.md），Surface 为 Colab A100-SXM4-80GB 两次 n=10＋n=17（原脚本 0 行修改，实验卡 EXPERIMENT_CARD_colab02.md、EXPERIMENT_CARD_colab06.md）。两平台不能称单平台完全相同环境。','','Surface 合并式：每变量每时效 RMSE_27(h)=sqrt((10×RMSE_10(h)²+17×RMSE_17(h)²)/27)，整体值为 h=1…72 的算术平均，与作者脚本 `mse_sum/count` 先开方再按时效求均值一致；不可直接平均两段整体 RMSE。相对差 = |我们−官方|/官方。','','| 变量 | 官方 n=27 | 我们 n=27 | 相对差 | 平台 |','|---|---:|---:|---:|---|']
for k,r in ref.items():
 o=ours[k];lines.append(f'| {k} | {r:.4f} | {o:.4f} | {abs(o-r)/r:.3%} | '+('CRC A10' if k in air else 'Colab A100')+' |')
lines+=['',f'判据（10-19 17:50 原定）：≥13/14 项相对差 ≤10%，没有任何一项 >25%；本次 {within}/14 ≤10%，{over} 项 >25% → '+('过。' if within>=13 and over==0 else '不过。'),'原先 n=10 与官方 n=27 的「部分复现不过」（9/14）是不同样本读法，保留，不被此表覆盖。','', '## Surface 逐起报 RelativeL2 loss','','原测试脚本仅每 10 个 batch 打印一次逐起报 loss；其余逐例 loss 没有写盘，不能由聚合 RMSE 逆推。以下仅列能从我们与官方 run.log 同时读到的起报；对其余起报标为不可比，而非虚构。','','| 起报日 | 官方 run.log loss | 我们 | 相对差 |','|---|---:|---:|---:|']
off=(b/'colab01/source/AERO_ODE/AERO_Surface_WD/Test_Surface_Rmse_00z_wb/run.log').read_text()
prior=(b/'colab02/final/surface.log').read_text()
def getloss(text):
 return {int(day):float(loss) for day,loss in re.findall(r'Batch\s+\d+/\d+\s*\|\s*Init:\s*2024/04/(\d{2})/00\s*\|\s*Loss:\s*([\d.]+)',text)}
ol=getloss(off);wl=getloss(prior)|getloss(log)
for day in range(1,28):
 o=ol.get(day);w=wl.get(day)
 if o is not None or w is not None:
  lines.append(f'| 04-{day:02d} | '+(f'{o:.5f}' if o is not None else '未记录')+' | '+(f'{w:.5f}' if w is not None else '未记录')+' | '+(f'{abs(o-w)/o:.3%}' if o is not None and w is not None else '不可比')+' |')
lines+=['','脚本输出日志缺逐起报 loss 的日次不列逐日数字；若需全 27 日 loss，需新的明确授权改日志或由不可逆聚合之外的原始记录获取。','','代码及许可：AERO-ODE https://github.com/ZZzzzZZZV/AERO_ODE （Apache-2.0）；数据/权重 https://huggingface.co/datasets/ZhangJing1106170090/AERO_ODE_Case_Data （CC-BY-NC-4.0）。']
out=b/'repro_table_n27.md';assert not out.exists(),out
out.write_text('\n'.join(lines)+'\n');print('within',within,'over',over,'surface',ours['MSLP'],ours['U10'],ours['V10'],ours['T2m'],'output',out)
