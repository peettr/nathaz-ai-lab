"""Reproducible 14-variable comparison, using the official overall tables."""
import re
from pathlib import Path
base=Path(__file__).resolve().parent
repo=base/'colab01/source/AERO_ODE'
run=base/'colab02/final'
order=['Z300','Z500','Z700','Z850','Z925','T300','T500','T700','T850','T925','MSLP','U10','V10','T2m']
def parse(text,names):
 if names[0].startswith('Z'):
  sections=re.findall(r'AERO-ODE RMSE:\s*\nVariable\s*\|\s*AERO-ODE[^\n]*\n(.*?)(?=\nMEAN\s*\||\Z)',text,re.S)
 else:
  text=text.split('RMSE by Lead Time')[0]
  sections=re.findall(r'Variable\s*\|\s*Mean RMSE[^\n]*\n(.*?)(?=\n={4,}|\Z)',text,re.S)
 assert sections,'overall RMSE section missing'
 block=sections[-1]
 result={}
 for name in names:
  matches=re.findall(r'^\s*'+re.escape(name)+r'\s*\|\s*([0-9]+(?:\.[0-9]+)?)',block,re.M)
  if matches:result[name]=float(matches[0])
 return result
ref=parse((repo/'AERO_AIR_WD/Test_Data_Rmse_00z_wb/run.log').read_text(),order[:10])|parse((repo/'AERO_Surface_WD/Test_Surface_Rmse_00z_wb/run.log').read_text(),order[10:])
air=(run/'air.log').read_text();sfc=(run/'surface.log').read_text()
assert 'Evaluation Complete [00Z Only] (10 batches' in air
assert 'Evaluation Complete [00Z Only, Surface Variables] (10 batches' in sfc
assert [int(x) for x in re.findall(r'Batch (\d+)/10 \| Init: 2024/04/\d{2}/00',air)]==list(range(10))
ours=parse(air,order[:10])|parse(sfc,order[10:]);assert set(ours)==set(ref)==set(order)
rows=['# L26.4 官方西部复现对照（部分复现 n=10）','','数据来源：Zhang et al. (2026) AERO-ODE 仓库 commit 99516ae9cf 的 AIR/Surface 官方 run.log（2024-04、27 个 00Z 起报）；我们在 Colab NVIDIA A100-SXM4-80GB 上运行同仓库脚本，输入为作者 HF 案例数据的 2024-04 ERA5/HRRR。我们的起报日为 2024-04-01 至 04-10 每日 00Z，72 h；因此官方的 27 次平均与本次 10 次平均不是同一样本，差值不能单独归因于模型复现误差。','','相对差 = |我们−官方|/官方，按作者日志所列整体平均 RMSE（非 6h 列）计算。','', '| 变量 | 官方 run.log (n=27) | 我们 (n=10) | 相对差 |','|---|---:|---:|---:|']
within=0;over25=0
for name in order:
 r=ref[name];o=ours[name];d=abs(o-r)/r
 within+=d<=.10;over25+=d>.25
 rows.append(f'| {name} | {r:.4f} | {o:.4f} | {d:.2%} |')
passed=within>=13 and over25==0
rows.extend(['',f'判据（10-19 17:50 原定）：≥13/14 项相对差 ≤10%，没有任何一项 >25%；本次 {within}/14 项 ≤10%，{over25} 项 >25%。部分复现（n=10）'+('过。' if passed else '不过。'),'此判定只针对本次十个起报与官方 27 个起报的比较，不断言官方代码/权重有缺陷；德州零样本未在本委托内执行。','','数据及许可：官方代码 https://github.com/ZZzzzZZZV/AERO_ODE （Apache-2.0），数据/权重 https://huggingface.co/datasets/ZhangJing1106170090/AERO_ODE_Case_Data （CC-BY-NC-4.0）；NeuralGCM https://github.com/google-research/neuralgcm （权重 CC-BY-SA-4.0）。'])
out=base/'repro_table_colab02.md';out.write_text('\n'.join(rows)+'\n');print('within10',within,'over25',over25,'pass',passed,'output',out)
