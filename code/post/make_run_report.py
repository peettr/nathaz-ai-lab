"""Generate a bounded post-job report from verified immutable metrics."""
import json
from pathlib import Path
r=Path(__file__).parent
c=json.loads((r/'COMPARISON_3710432.json').read_text())
m=json.loads((r/'out_3710432/meta.json').read_text())
keys=('n','n_tke','FAC2','q_abs025','q_rel025','r','NRMSE_range','NRMSE_mean','TKE_FAC2','TKE_r','mean_ratio','mixed_solid')
lines=['# Case A dx10 v2 后处理作业 3710432 核查（11-11 美东）', '',
 'ComputeOps CO-e937fca4；TACC skx-dev，Slurm COMPLETED 0:0，00:00:02；run.exitcode=0；rc-job --kind post 提交阶段回执「已登记」。运行根 `/scratch/04448/[用户]/r24_luw/caseA_dx10_v2_post/`；未重跑求解器。', '',
 '求解日志 `caseA_dx10_v2/caseA_dx10/proj_temp/20261111185024_lbm.log`（完整前缀见 source_check.json）：6400 步、550 平均样本、Task finished、日志没有 NaN/Inf token。源 VTK 7,142,083 B，SHA256 '+m['source_sha256']+'。与原生 flags 门禁不同，本次只读 VTK fluid，依据 Lead 11-11 的事先改判。', '',
 '运行输出：五件 gzip NPY、小端 float32、(z,y,x)=(39,70,109)；本地八文件与远端 SHA256 全匹配，五件全场逐值有限，NPY 头及未压缩长度匹配；每件<200 MB。meta.json 记载源、origin=(0,0,-30)、spacing=10.057143、有效地面标签 -4.857143 m、统计窗、字段定义。五件 fluid 是 VTK 标量，非原生 flags。', '',
 'IoU 的中高建筑截面在 (10.057143,10.057143,0) m 达到 0.87890625，按掩膜而非性能指标选择水平偏移。4/40 m 对应 VTK 标签 -0.857143/35.142857；8/80 m 为标签 3.142857/75.142857。竖剖面逐点将原高度加有效墙面标签。U=sqrt(u²+v²+w²)/UH，k=解析 TKE/UH²。FAC2 是 0.5 obs ≤ pred ≤ 2 obs 的比例，q_abs025 是 |pred-obs|≤0.25，q_rel025 是 |pred-obs|≤0.25|obs|；r 是 Pearson，NRMSE 按 obs 极差或均值归一，mean_ratio=Σpred/Σobs。TKE 仅计 |obs_k|>0.05 的点。', '',
 '下表为同一指标公式，但不是同高度的严格网格比较：2/4 m 采用已有档案的原 VTK 标签高度和 plus_xy 偏移；10 m v2 是有效墙面离地高度。旧 0b 错误地板的 10 m 指标未入表。8/80 m 是与原 4/40 m 观测比较的错高诊断。', '',
 '| 测面 | 网格/来源 | '+' | '.join(keys)+' |',
 '|---|---|'+'|'.join(['---']*len(keys))+'|']
for row in c['metrics']:
 for name,slug in [('2m_legacy_label_not_wall_matched','2 m 历史标签'),('4m_legacy_label_not_wall_matched','4 m 历史标签'),('10m_v2_wall_matched','10 m v2 有效墙面')]:
  d=row[name];lines.append('| '+row['plane']+' | '+slug+' | '+' | '.join(f'{d[k]:.4f}' if isinstance(d[k],float) else str(d[k]) for k in keys)+' |')
lines += ['', '严重采样限制：10 m 有效离地 4 m 的标签 -0.857143 低于第一流体中心约 0.171429，全部 60/60 个选中点的八角插值含固体；该行虽是按冻结公式算出的诊断值，不得充当无污染的行人高度模型精度。中心竖剖面 9/66、40 m 4/60 也混入固体。高度差和固体插值使本表不能直接推断网格收敛或近壁误差原因。', '',
 '本地数据目录 `out_3710432/`（五件场、samples、metrics、meta、output.sha256）；完整并列表 `COMPARISON_3710432.json`；核验代码 `verify_and_compare.py`，本实验卡 `EXPERIMENT_CARD.md` 第⑤栏。需要无固体污染的 4 m 科学比较，应先冻结并执行采样规则、重新对齐 2/4 m 真离墙高度；不修改这次留存结果。']
(r/'RUN_post_3710432.md').write_text('\n'.join(lines)+'\n')
print('wrote',r/'RUN_post_3710432.md', 'rows',sum(1 for x in lines if x.startswith('| ') and '网格/来源' not in x))
