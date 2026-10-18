import json, statistics as st
from pathlib import Path
p=Path(__file__).parent
D=json.loads((p/'metrics_v3.json').read_text())
assert len(D['runs'])==12
lines=['| N | 方法 | RMSE 均值±种子SD | 逐例中位R²均值±种子SD | 理想化 R² / RMSE | 真实 R² / RMSE |', '|---:|---|---:|---:|---:|---:|']
for n in (50,100,200,400):
 for method in ('B0','B1','B2','UNet') + (('OldAKO',) if n==400 else ()):
  a=[r['methods'][method]['summary'] for r in D['runs'] if r['N']==n]
  def fmt(key):
   x=[v[key] for v in a]
   return f'{st.mean(x):.4f}±{st.stdev(x):.4f}'
  lines.append(f'| {n} | {method} | {fmt("rmse")} | {fmt("median_r2")} | {fmt("ideal_median_r2")} / {fmt("ideal_rmse")} | {fmt("real_median_r2")} / {fmt("real_rmse")} |')
a=[r for r in D['runs'] if r['N']==400]
lines.append('\n测试几何 bootstrap 95% CI（N=400，各种子分别按几何重采样 1000 次）：')
for r in a:
 for m in ('B1','UNet','OldAKO'):
  z=r['methods'][m]['summary']
  lines.append(f"种子 {r['seed']} {m}: RMSE {z['rmse']:.4f} [{z['rmse_ci95'][0]:.4f},{z['rmse_ci95'][1]:.4f}]；中位R² {z['median_r2']:.4f} [{z['median_r2_ci95'][0]:.4f},{z['median_r2_ci95'][1]:.4f}]。")
lines.append('\n逐几何胜率（U-Net 对 B1，种子 17/42/73）：'+', '.join(f"{r['methods']['UNet']['win_vs_B1']:.0%}" for r in a))
lines.append('缺风向 9 个测试算例剔除后 N=400 U-Net 中位 R²：'+', '.join(f"{r['known_direction_only']['UNet']['median_r2']:.4f}" for r in a))
(p/'summary_v3.txt').write_text('\n'.join(lines)+'\n')
print('\n'.join(lines))
