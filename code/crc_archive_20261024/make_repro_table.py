"""Programmatically build the 14-variable official-vs-measured table.
No measured values are invented when the GPU job exits before inference.
"""
import re
import sys
from pathlib import Path

repo = Path('/groups/kareem/[用户]/L26_4_AERO_ODE_20261019/repo/AERO_ODE')
run = Path('/groups/kareem/[用户]/L26_4_AERO_ODE_20261019/official_run_01')
order = ['Z300','Z500','Z700','Z850','Z925','T300','T500','T700','T850','T925','MSLP','U10','V10','T2m']
air = (repo/'AERO_AIR_WD/Test_Data_Rmse_00z_wb/run.log').read_text()
sfc = (repo/'AERO_Surface_WD/Test_Surface_Rmse_00z_wb/run.log').read_text()
measured_air = (run/'air.log').read_text() if (run/'air.log').exists() else ''
measured_sfc = (run/'surface.log').read_text() if (run/'surface.log').exists() else ''

def parse(text, names):
    result = {}
    for name in names:
        matches = re.findall(r'^\s*'+re.escape(name)+r'\s*\|\s*([0-9]+(?:\.[0-9]+)?)', text, re.M)
        if matches: result[name] = float(matches[-1])
    return result

ref = parse(air, order[:10]) | parse(sfc, order[10:])
ours = parse(measured_air, order[:10]) | parse(measured_sfc, order[10:])
assert len(ref)==14, (ref, len(ref))
text = ['# L26.4 官方西部复现对照（失败作业，n=0）', '',
        '偏离原计划：CRC 1593298 在模型启动前因 GPU 绑定变量缺失退出；下列「我们」均为未测，不是 0，不能算相对差，也不能判官方复现。', '',
        '定义：相对差 = |我们−官方|/官方，仅在同变量有实测值时计算。官方列由 commit 99516ae9cf 两份 `Test_*/run.log` 程序解析；其参照为 2024-04、27 个 00 UTC 起报、72 h。', '',
        '| 变量 | 官方 run.log | 我们 | 相对差 |', '|---|---:|---:|---:|']
for name in order:
    v=ref[name]
    measured=ours.get(name)
    text.append(f'| {name} | {v:.4f} | {measured:.4f} | {abs(measured-v)/v:.2%} |' if measured is not None else f'| {name} | {v:.4f} | 未测 | 不适用 |')
text.extend(['', '实测有效起报数：0；原判据要求 ≥7（部分复现）或 27（全月），故未达可判阈值。',
             '数据源：Zhang et al. (2026) AERO-ODE 官方 run.log，https://github.com/ZZzzzZZZV/AERO_ODE （Apache-2.0）；2024-04 ERA5/HRRR 公共样本 https://huggingface.co/datasets/ZhangJing1106170090/AERO_ODE_Case_Data （CC-BY-NC-4.0）。'])
(run/'repro_table_blocked.md').write_text('\n'.join(text)+'\n')
print('official=',len(ref),'measured=',len(ours),'output=',run/'repro_table_blocked.md')
