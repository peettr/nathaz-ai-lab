#!/usr/bin/env python3
"""Render delay-6 h addendum to final_report_v2 from delay6_v2/score/scores.csv and score_v2/gate.json."""
from pathlib import Path
import json,hashlib,pandas as pd
R=Path(__file__).parent
s=pd.read_csv(R/'delay6_v2/score/scores.csv');g={x['fhr']:x for x in json.loads((R/'score_v2/gate.json').read_text())['D']}
L=['# M7 final_report_v2 补节：预注册 7.6 GFS 延迟 6 h 重选运行敏感性（只报不判）','',
'口径（事后写定 11-08，读检验期前冻结于 `delay6_v2/README.md`）：issue 保持 init+4 h；6 h 发布延迟下改用前一次运行 init−6 h、取 fhr+6 到同一 valid；训练与检验两边特征都重选，按原 fhr 档重新 LOSO 拟合；观测与检验人口与主判逐行相同；日块 1000 次，[Q0.025, Q0.975]。','',
'| fhr / L (h) | n / 日 | D2 MAE | FXD2 MAE | 延迟 6 h D [95%] | 主判（4 h）D [95%] |','|---|---:|---:|---:|---:|---:|']
for r in s.itertuples():
 x=g[int(r.fhr)];L.append(f'| {r.fhr} / {r.L} | {r.n} / {r.days} | {r.mae_d2:.3f} | {r.mae_fxd2:.3f} | {r.D:.4f} [{r.lo:.4f}, {r.hi:.4f}] | {x["point"]:.4f} [{x["lo"]:.4f}, {x["hi"]:.4f}] |')
L+=['',f'读法（描述性，不作新闸门）：延迟 6 h 时四档 D 的 95% 上界仍均 <0，相对降幅 {100*abs(s.D).min():.1f}%–{100*abs(s.D).max():.1f}%，比 4 h 主判略小，fhr24/48 缩小更多。此为单配置、单冬季的敏感性，不称「对发布延迟稳健」的一般结论。',
'Colab：CPU 抓取 + A100 推理，按假设费率估约 10.0–10.3 CU（非账单），≤12 CU；0 SU。']
out=R/'final_report_v2_addendum_delay6.md';assert not out.exists();out.write_text('\n'.join(L)+'\n')
print(out,hashlib.sha256(out.read_bytes()).hexdigest())
