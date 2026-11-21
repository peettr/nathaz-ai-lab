#!/usr/bin/env python3
"""Render correction-by-addition for historical R23.2a BSS reference; preserve v1."""
import json
from pathlib import Path
D=Path(__file__).resolve().parent/'m2_2023_v1/assembled_v1'
a=json.loads((D/'descriptive_r232a_v1.json').read_text());b=json.loads((D/'descriptive_v2.json').read_text())
L=['# R23.7 结果附注补充 v2：2022 气候率的两种实现（仅描述）','',
'本补充与 results_v1_附注.md 一起阅读，原文件不覆盖。附注 v1 的 BSS/q22 是「2022 六臂共同配对训练样本的单一总体事件率」；它确实只用 2022 观测，但不是 R23.2a 原脚本的拟合气候预测参照。不可将两者视为相同算法。',
'R23.2a run_verify_v2.py 第 190–194 行是以 2022 年 GRAP_v100_GFS 原档全部 8044 条训练记录中的 climatology 特征拟合一个 ≥8 m/s 的逻辑回归，再在检验配对键取逐记录 p_clim（原脚本的 BSS 对照）。此补算依该逻辑，在 R23.7 的共同样本上计算参照 Brier；所有参数只从 2022 拟合，2023 观测只用于检验。附注 v1 已并列的 BSS/q23 是 2023 检验样本的常数事件率，只是事后描述参照。三个数的分母/参照不同，不能直接解释为模型训练变化。','',
'|样本|时效 h|臂|BSS/2022 pooled q22|BSS/R23.2a 2022-fitted climatology|BSS/2023 sample q23|','|---|---:|---|---:|---:|---:|']
for cohort,leads in a['cohorts'].items():
    for lead,cell in leads.items():
        for arm,r in cell['arms'].items():
            v=b['cohorts'][cohort][lead]['arms'][arm]
            L.append(f'|{cohort}|{lead}|{arm}|{v["BSS_vs_2022_climatology"]:.6f}|{r["BSS_vs_R23_2a_2022_fitted_climatology"]:.6f}|{v["BSS_vs_2023_sample_rate"]:.6f}|')
L += ['','生成来源：descriptive_r232a_v1.py / descriptive_r232a_v1.json（2022 拟合 R23.2a 参照）、descriptive_v2.py / descriptive_v2.json（2022 pooled 与 2023 样本参照）。这些全是事后描述，不改 C、区间或「分不出」总判定。','']
p=D/'results_v1_附注_补充v2.md';assert not p.exists();p.write_text('\n'.join(L))
print(json.dumps({'path':str(p),'table_rows':sum(len(c['arms']) for x in a['cohorts'].values() for c in x.values())},ensure_ascii=False))
