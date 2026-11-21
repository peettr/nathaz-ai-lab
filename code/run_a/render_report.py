#!/usr/bin/env python3
"""Format Colab-produced preflight counts; no scientific model computation."""
import json,csv,hashlib
from pathlib import Path
p=Path(__file__).parent
items=json.loads((p/'a_preflight.json').read_text())
station_rows=list(csv.DictReader((p/'a_preflight_rows.csv').open()))
assert len(items)==15 and len(station_rows)==sum(x['metadata_primary'] for x in items)
assert {x['event'] for x in items}=={x['event'] for x in station_rows}
assert all(x['model_evaluable']=='no' for x in items if x['strict_unfittable_nodes'])
bad=[x for x in items if x['strict_unfittable_nodes']]
core=[x for x in items if x['within_landfall_pm12h_unfittable']]
remaining=[x for x in items if not x['strict_unfittable_nodes']]
header='| 事件 | 主池元数据站 | 8–12 m 元数据站 | ±19h 输入内不可拟合 BEST 节点 | ±12h 内节点 | 逐站误差 |\n|---|---:|---:|---:|---:|---|\n'
table=''.join(f"| {x['event']} | {x['metadata_primary']} | {x['metadata_parallel']} | {len(x['strict_unfittable_nodes'])} | {len(x['within_landfall_pm12h_unfittable'])} | {'不可评（事件输入）' if x['strict_unfittable_nodes'] else '未算（提前停闸）'} |\n" for x in items)
sha=lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
inputs=json.loads((p/'inputs_v2'/'manifest.json').read_text())
paths=[p/'inputs_v2'/f for f in ('tracks.csv','stations.csv','observations.csv','landfalls.csv','manifest.json')]
manifest='\n'.join(f"- `{q.relative_to(p)}` sha256 `{sha(q)}`，{q.stat().st_size} bytes" for q in paths)
freeze=Path('./22_Lab/06_Logs/b_tc/v2d/prereg')
for filename,expected in [('PREREG_v2.md','ed028aed21bdf8bba6115007551cac86bd43ecfdaeca6f3a4aa3deda7325c648'),('PREREG_v2_ADDENDUM_A1.md','0933907b2f7ce82c10e8d7809afd43f10ff6063fda9df2df0a7d21ecb0893abe'),('homr_audit_frozen.csv','e62b8a1e4b7f4e8da76b42d7fa80f855bcf5d574d69b4b59bc35135a0a097264'),('rmw_adapter.py','5238d8db0b1c4e89675cd1569c66449cf0485764b2fa3b9d9c74b63d387398ca'),('chain_a_v2.py','d9b35eb15c4b415aba08f0de83fcb426b08510d51099c34e2f303ee6b636e283')]:
 assert sha(freeze/filename)==expected,(filename,'frozen hash changed')
assert (p/'a_original.exit').read_text().strip()=='143'
text=f'''# R23.3a-03 (a) 链闸：输入必要条件未满足，按冻结版不判闸

执行时间：10-21 11:23–11:33 美东；只涉及 (a)，未启动 (b)(c)。冻结依据：`../prereg/FREEZE.md` 与 `FREEZE_SHA256.txt`（冻结原文件 hash 校验全部通过）；A1 冻结站表为 `homr_audit_frozen.csv`。结果仅限本次 15 事件、此份 BEST ATCF 和 IEM 抽取配置，不是对任何模型本体的优劣判断。

定义先行：单站误差 e = pred_peak_10m/obs_peak_10m − 1；全站中位偏差 B = median_station(e)；全站中位绝对误差 M = median_station(|e|)。±20% 闸仅在 15 个意向事件各有至少 3 个三链共同可评站、(a) 模型和观测峰均有效时判，边界计入；8–12 m 池只描述，不单独判闸。若事件输入关键节点风圈拟合无解，预注册 19、23 行规定不得回退，该事件站退出误差计算；没有误差时 B、M 不定义，不能报成 0% 或「未过 ±20%」。

首次冻结原版 `chain_a_v2.py` 已在 Colab CPU 启动 (a)（`--lead-frozen`），但独立的无配对输入预检发现确凿的先决阻断，遂向该本任务进程发送 SIGTERM；`a_original.exit=143`，没有生成 `a_original_rows.csv`，没有看见或计算任何 v2 站点误差。该停跑不是原程序自行完成全部 15 个事件的回执。预检复现冻结 `rmw_adapter.fit_rmw()` 的硬必要条件：每个 BEST 节点需要至少 2 个不同阈值 k<Vmax，各≥2 个正象限；只要某节点不足，冻结 `build_track()` 第 79–84 行就将整个事件列为不可评，不跨节点/跨链补圈。表中“不可拟合”仅由阈值与象限原始字段证出；尚未做 H08 数值拟合，其他失败原因可能增加，不会减少已证阻断。

主口径：元数据站 {sum(x['metadata_primary'] for x in items)} 条站–事件、{sum(x['metadata_primary']>=3 for x in items)}/15 事件元数据≥3；{len(bad)}/15 事件在当前 ±19h BEST 输入里有缺阈值节点，其中 {len(core)}/15 的缺阈值节点落在登陆±12h 核心窗，故即便只保留核心输入也无法靠剪裁凑足 15×3。无此项硬阻断的 {len(remaining)} 个事件（{', '.join(x['event'] for x in remaining)}）只是“待模型及峰窗复核”，并非已可评站。三链共同可评站数尚未运行 (b)(c)，不可据单链候选宣称共同交集。严格主闸判词：不判闸；(a) 的 B/M/±20% 均不可评，不解释成未过阈值。采用 A1 前的站类读法主池仅 14/15 元数据≥3（HELENE 两站），也同样不判闸（见 `../prereg/PREREG_v2_ADDENDUM_A1.md` 第 8 行）。

并列 8–12 m：元数据站 {sum(x['metadata_parallel'] for x in items)} 条站–事件、{sum(x['metadata_parallel']>=3 for x in items)}/15 事件≥3；它只描述。与主池共用同一 (a) BEST 输入，{len(bad)} 个事件的全部站因事件级输入缺阈值而不可评，其余 {len(remaining)} 个事件也没有完成预测/观测峰窗评估；没有并列池 B/M 数字，更不做它的 ±20% 闸。

{header}{table}

逐站明细：`a_preflight_rows.csv`，每条冻结主池站均标 cohort 与原因；`not_assessed_no_model_peak` 不等同于“已证截尾”。没有 t*，所以不能按冻结版四格峰窗判断截尾，也不能合法给出逐站观测峰下界/有限上界；所有下界留空、有限上界不可定。当前预检的 12 个事件是关键节点输入不可评，不把它们冒充观测截尾。所有站高度均是 2025 NWS 清单代理、历史事件日未证实（见冻结 A1）。各站具体拒绝节点和时间在 `a_preflight.json`；IDALIA 的坏节点全在±12h外，其余事件亦有部分窗外节点，均与核心窗内节点分别列出。

输入和来源：BEST 压缩 b-deck 来源与各自原包 sha256、IEM 每组 URL 与下载行数、站点坐标 IEM `_ASOS` GeoJSON 查找、缺失检查均在 `inputs_v2/manifest.json`；该文件是 Colab 实际拉取后的审计。Natural Earth 10m land zip 在 Colab 下载的 sha256 为 `e547d749445eaa0964aba76738090ec88f5e63c4585122170f98c67a7ea922dc`（3,269,070 bytes），本次没有产出风场值。数据集授权与二次分发须按项目目录登记核对；这里仅内部审计。

{manifest}

执行记录：`inputs_v2/a_stage_v2.log`、`inputs_v2/a_stage_v2.exit`、`a_original.log`、`a_original.exit`，Colab 会话 `r233a-a-1021-cpu` 已关闭并在 sessions 中消失，未触及其他会话。前一次失败的 ATCF URL 构造诊断保留在根目录 `a_stage.log`、`manifest.json`、`tracks.csv`，它们不得混进有效输入；修复只改运行区的输入准备脚本，详情在 `POST_FREEZE_CHANGES.md`。账户在共享 A100 会话同时运行下的余额变化不能归因于本 CPU 会话；本次未独立计量 CU，按 CPU 会话约 10 分钟及同时账户费率不能从共享差额证明精确 CU。停止时间 11:33，美东；小于 5 CU 的预算上限无证据被触发。
'''
(p/'RESULTS_a_corrected.md').write_text(text)
print('generated',p/'RESULTS_a_corrected.md','events',len(items),'rows',len(station_rows),'blocked',len(bad),'core',len(core),'clear_pending',len(remaining))
