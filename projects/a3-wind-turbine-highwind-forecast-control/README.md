# 风机高风速预报与调控

**分组**：AI 气象 / 气候大模型与风工程　**状态**：搁置　**时间**：2026-10-14 – 2026-10-16

## 阶段结论（测试性质，非正式结题）

10-15 分段 D：偏心路径预视停机降偏航力矩约 25%，近中心塔底反向弯矩恶化 14% → 按预定规则搁置；10-16 旧风场 4/4 逐字节一致

## 原始任务



## 项目报告

# A3 风机高风速预报与调控

## 目标
风机高风速下预报与主动调控（变桨/偏航/降载、激光雷达前馈、塔架/叶片减振）的已有工作与空白，判断能否切入（极端/非平稳来流下的前馈与减振上限）。

## 当前状态
**搁置（10-15 07:5x）**，依据。
- 一句结论：在解析下击暴流 + 合成湍流 + 离线触发的模拟里，用机舱激光雷达提前约 7 s 触发停机，在风向急转、偏航跟不上的偏心路径上降塔顶偏航力矩约 25%、叶根负峰约 15%；但在近中心路径会使塔底反向弯矩恶化约 14%，按预定规则不过。变桨前馈部分因工具链未过稳态湍流文献闸门早已搁置。
- **为什么搁置**：(1) 近中心路径负向载荷恶化超过预定 10% 限；(2) 偏心路径的"通过"带着未解释的实际偏航超速（0.44–0.46°/s，设定 0.3°/s）和 LOS 湍流近似；(3) 机理只是"停得早"，价值取决于能否提前识别下击暴流，属于检测/预报问题。
- **缺什么**：真实下击暴流入流（CM1/LES）、在线触发、偏航动力学核实、更缓的停机顺桨策略、可用的 OpenFAST 5.x 激光雷达前馈实现。
- **什么情况下重启**：(a) 修正偏航超速后偏心路径收益仍在，且找到不恶化塔底反向弯矩的停机方式；(b) CM1 线或数字孪生风洞线能给出真实下击暴流风场；(c) 有在 OpenFAST 5.x 上验证过的激光雷达前馈实现（重启变桨前馈部分）；(d) 有具体风场的下击暴流停机需求。
- 迁移：10-15 起本节点随「AI 气象大模型」项目管理；试验记录仍在；工作站 旧运行根已归档 TACC。

## 边界（10-14 18:3x 母项目更正）
- ~/lab_a3/downburst_ff：10-15 根 Lead 按 Liang Hu 授权清理 工作站（ 第 15–16、26 行），分段 A/A2/B 的 OpenFAST 输出、pilot、日志与 run_nrel5mw_* 共 8188 个文件 11.39 GB 已搬到 （逐个核对文件数与字节后删本机）；env、src、第三方源码与编译产物已删（可重建）。以后复核从 TACC 取，不拉回 工作站。

## 已定决定
- 10-14 开工安排 → 
- 10-15 六审 裁决：提案退回 → 
- 10-14 审查 裁决 → 
- 10-14 DR 额度用完，按 Grok+Lead 核对先送审、并行冒烟测试 → 

## 试过与结果
| 日期 | 做了什么 | 结果一句 |
| --- | --- | --- |
| 10-15 | 分段 D：修正湍流、机舱 LOS 1D、12 种子、简单无雷达触发 S1–S4（Colab，360+36 次） | 近中心：偏航降 20.9% 但塔底负弯矩恶化 14.4% → 不过；偏心：偏航降 24–25%、叶根负峰改善 14–15% → 计算通过，但实际偏航超速未解释；风向率触发同等降载但 36/36 误停 → 按预定规则搁置 |
| 10-15 | 六审 （5 有保留支持、1 不支持） | 中位降幅属实但 1/6、2/6 种子反升；塔底前后负峰恶化（近中心中位 24%，偏心 6/6 种子）、2 种子叶根负峰翻倍；湍流各向同性、未按平移速度缩放；上游信号非真实激光雷达；简单无雷达触发未排除 → 提案退回 |
| 10-15 | 分段 C：降阈值 22/20/18 m/s 反事实 + 常规湍流误停（Colab 约 0.1 CU） | 降阈值要么降幅不够、要么误停 17–18/18；预视 1D 误停 10/18（25 m/s 基准 9/18）→ 判据"预视有独特价值"；保留：3 s>25 m/s 规则本身误停多、结果不单调、离线触发 |
| 10-15 | 分段 B 停机组 G0–G4（96/96，Colab 补 70，约 3–4 CU） | 预定判据通过：现实 1D 预视停机相对即时停机降塔顶偏航力矩中位 15.5%/24.2%，塔底与叶根基本不变；实际提前 5.5–9 s，收益机制=停得早；旧 26 个原始风盒已不在（流程级溯源确认：…/RESULTS_B_stop_v4_source_check_20261015.md；分段 C 顺带在 Colab 独立重算） |
| 10-15 | 前馈闸门诊断：自写链时移扫描 + 作者参考链（Task52，OpenFAST 5.0 通道桥接） | 两链都没过：时移最好 −2.3%（单种子）；参考链转速标准差反升 36–63%；BTS 约 7 s 时间偏移实测确认 → 前馈部分搁置 |
| 10-15 | 前馈改为桨距率进 PI 积分器 + IEC NTM 16 m/s 文献闸门（3 种子，Colab 约 0.3 CU） | 闸门未过：完美前馈转速标准差反升 14–18%（文献预期下降）；派时移扫描 + 作者参考链对照 |
| 10-14 | 分段 B Colab 续跑（单种子 112，G5–G8；复算 工作站 工况差 0.000%） | G6 现实 2D −13%、G7 完美同提前量 +8%、G8 +33%——红旗；Lead 诊断前馈绝对桨距偏置重复计稳态桨距，A2_guo_v3 的 12–24% 同样作废；约 0.03 CU |
| 10-14 | 分段 B（部分，26/96，工作站） | 湍流全场 + 独立上游预视链跑通；近中心 3–4 种子：现实预视停机降塔顶偏航力矩约 18–38% 但叶根负峰变差，未判定；23:00 因 C 盘暂停 |
| 10-14 | 分段 A2 补：Guo 2023 前馈律（近中心） | 现实 1D/2D 前馈降塔底合成 12%/24%，完美（提前 2–3 s）仅 1.6%——疑为提前量效应（提前降额），变桨前馈组加回分段 B 分离提前量与信息 |
| 10-14 | 分段 A2：偏航接通 + 即时阈值停机基准（20/20 次，29 min） | 即时停机本身降塔底合成 15%/37%（非预视）；变桨前馈 ≤1% 退出；偏心路径（偏航 0.3°/s 跟不上 111° 风向旋转——物理限制，Lead 判有效）预视提前停机相对即时停机降塔顶偏航力矩 16–67%、叶根负峰 16–41%，塔底合成 ≤3% |
| 10-14 | 分段 A 附加：现实/完美收益比例（v10 探索） | 变桨前馈完美收益多 <3%，比例多为负或不适用；停机现实 1D/完美 ≈0.8–1.1 但基准是 50 s 规则；近中心提前停机使塔底前后负峰幅值大增（−1275%），停机本身带来反向载荷，A2 须同时看正负峰 |
| 10-14 | 分段 A：确定性下击暴流 24/28 次（v10） | 变桨前馈完美仅 −0.9%/−3.1%、现实反升；Case III 偏航失效作废；停机收益疑来自取消 50 s 等待而非预视 |
| 10-14 | ROSCO 2.10.6 隔离副本加前馈注入口（Apache-2.0） | 同一二进制反馈/前馈 30 s 人工脉冲试跑，变桨差最大 3.9°，接口有效；非下击暴流，无载荷结论 |
| 10-14 | 研究前馈链 Linux 移植（WRAPPER→LDP→FFP→改版 ROSCO 2.6.0）+ Nguyen 2012 解析下击暴流场 | 控制器链 10 s 试跑正常；解析场 1D/2D 预视的 25 m/s 阈值提前约 8.6/17.2 s（几何量，非控制收益）；全矩阵外推 24 h 超闸门，未出载荷结果 |
| 10-14 | OpenFAST v5.0.0 + ROSCO 2.10.6 本地冒烟（conda-forge，60 s 跑通 30–38 s 墙钟） | 工具链可用；原版 ROSCO 无外部预视前馈接口，需 MSCA-LIKE（MIT）链或自加前馈项；IEA Task 52 仓库无许可证不用 |
| 10-14 | Grok 快查 + Lead 核对 | 稳态 LAC 成熟；下击暴流/阵风锋下预视前馈未找到先例 |

## 参数来源表
| 参数 | 取值 | 来源或"假设" | 查过哪些地方 |
| --- | --- | --- | --- |
| 停机触发规则 | 超 25 m/s 持续 10 转或 50 s | Nguyen 2012 PDF 第 112–113 页 | 原文 |
| 下击暴流形状函数 | α=2, c1=0.22, c2=2.75 | Nguyen 2012 PDF 第 66 页 Eqs. 3.2–3.7（ideas 核） | 原文 |
| Case I / III 参数 | Urm=47, Utrans=12/14, zm0=90/70, rm0=1000/610, y0=−100/−610 等 | Nguyen 2012 PDF 第 114 页表 4.4（ideas 核） | 原文 |
| 环境风 | 90 m 处 12 m/s，剪切指数 0.2 | Nguyen 2012 PDF 第 83 页、第 79 页 Eq. 3.24 | 原文 |
| 湍流强度 ε | 0.1 | Nguyen 2012 PDF 第 71 页 Eq. 3.12 | 原文 |
| 偏航限速 | 0.3°/s | Lu 2019 与 Nguyen 2012（审稿人引用，待 ideas 核 Jonkman 2009） | 待核 |
| 变桨限速 | 8°/s | NREL 5 MW（审稿人引用，待核 Jonkman 2009） | 待核 |

## 未决与下一步
- 已搁置（10-15），不派新试验；转正提案草稿作废。审计已闭合：旧 26 个工况 Colab v4c 重算七项指标 26/26 一致；10-16 TACC 归档旧 wind.bts 与 v4c 风盒 4/4 逐字节一致。无遗留待办。
- ~/lab_a3/downburst_ff：10-15 根 Lead 按 Liang Hu 授权清理 工作站（ 第 15–16、26 行），分段 A/A2/B 的 OpenFAST 输出、pilot、日志与 run_nrel5mw_* 共 8188 个文件 11.39 GB 已搬到 （逐个核对文件数与字节后删本机）；env、src、第三方源码与编译产物已删（可重建）。以后复核从 TACC 取，不拉回 工作站。
- Deep Research 额度恢复后补跑，重点确认"未找到先例"。
- PUBLIC_CITATIONS.md 已补 OpenFAST、ROSCO、NREL 5 MW、MSCA-LIKE、Nguyen 2012/2014。

## 已有工作与空白（审查 后定稿 v2）
| 方向 | 代表工作与出处页码 | 成熟度 | 我们能否切入 | 需要什么 |
| --- | --- | --- | --- | --- |
| 稳态湍流激光雷达前馈（集体变桨） | Bossanyi 2014 JPCS 555:012011；Guo 2023 WES 8:149 §5.2（塔底前后弯矩 DEL 至多 −16.7%，22 m/s 不稳定层结）；Schlipf 2018 IEA Task 32 | 成熟→早期商用 | 否 | — |
| IEC 极端阵风下前馈/检测降额 | Schlipf & Raach 2016 JPCS 753:052011（摘要：显著降塔底极值）；Haizmann 2018 DOI 10.1088/1742-6596/1037/3/032025、Hagemann 2017 DOI 10.18419/opus-9333（未核） | 发展中 | 弱 | — |
| 阵风锋/阵风时空演化下风场级预观测+提前偏航/IPC | Zhang 等 2026 Energy DOI 10.1016/j.energy.2025.139730（仅摘要级，审稿人 A 提供） | 发展中 | 待读全文 | 全文 |
| 下击暴流下风机载荷与反馈控制、超限停机 | Nguyen 2012 学位论文（PDF p.112–113 停机规则 50 s；p.133/期刊页 116 变桨+偏航不足、停机来不及）；Nguyen & Manuel 2014 DOI 10.3390/en7106527；Lu 2019 Energies 12:2773（LES，五个稳定度工况）；Pratapa 2023 DOI 10.1115/1.4055076（PDF p.7–8 含湍流） | 发展中（载荷评估为主） | 能 | 解析下击暴流 4D 场 + OpenFAST |
| 预警后已停机（顺桨）的下击暴流动力/FSI | Ahmed 等 2022 DOI 10.1016/j.engstruct.2021.113440；2023 JSE DOI 10.1061/JSENDH.STENG-11923（本库 522APTGW 第 3 页"warning assumed"）；2023 ES DOI 10.1016/j.engstruct.2023.116779 | 发展中 | 否（已有） | — |
| **单机下击暴流来流下机舱激光雷达预视前馈；预视定停机时刻 T** | 未找到（Grok、Lead 2 次、审稿人 3 位检索） | 未找到先例（待 DR 补跑） | **能——本节点切入点** | IEAWindTask52/LidarAssistedControl（改版 ROSCO 2.6.0）+ 4D 场上游采样 |
| 预报驱动风场级停机/降额（小时–分钟） | Jia 2023 Electronics DOI 10.3390/electronics12214443、Li 2022 Atmosphere 13:451（未核） | 基本停机成熟、优化发展中 | 中（非本组强项） | A1 取数 |
| 塔架/叶片减振 | Fakhry 2026 综述 DOI 10.1177/14613484261437475（未核） | TMD/IPC 成熟、主动发展中 | 中（与 A2 共用） | 仿真链加 TMD |

**一句结论**：值得继续（窄口）。**最小试验**：（四组对比 + T 扫描，≥6 种子×2 路径，判据预先固定）。

## 文献依据
- **A3 专题索引（litwiki 10-14 建）**：。卡片：Guo 2023 （16.7% 为 DEL，期刊 p.167/PDF p.19 §5.2.3；塔/叶根/低速轴 DEL 降幅 3.0–16.7%/1.5–6.0%/1.7–5.0%，期刊 p.168）；Schlipf & Raach 2016；Nguyen & Manuel 2014；Nguyen 2012 （表 4.4 论文 p.97/PDF p.114，t0/t1 单位 min；停机规则 PDF p.112–113）；Lu 2019；Haizmann 2018 （完美 5 s 预视、降至额定 65%，PDF p.4）；Zhang 2026 仅元数据卡（不可引结果）；Pratapa 2023 卡 Z454567N 已改为"均值场 + 频域湍流"。
- 知识库已有（下击暴流×风机，均未精读或仅初读）：Pratapa, Nguyen & Manuel 2023（DOI 10.1115/1.4055076，非湍流轴对称下击暴流→5 MW 风机载荷，载荷依赖偏航/变桨控制状态）；Nguyen 2012 学位论文 "The influence of thunderstorm downbursts on wind turbine design"（未读）；Zhang 等 2015 微下击暴流风机模型试验；Ji 等 2025（附件身份待核）。
- 激光雷达前馈、风机减振：库内无卡片。

## Liang Hu 注

## 结果图

![nrel5mw rosco tower pitch](figures/nrel5mw_rosco_tower_pitch.png)
![nrel5mw rosco tower pitch 8ms](figures/nrel5mw_rosco_tower_pitch_8ms.png)
![nrel5mw rosco tower pitch 14ms](figures/nrel5mw_rosco_tower_pitch_14ms.png)
![wind probe deterministic](figures/wind_probe_deterministic.png)
![licensed ff pulse](figures/licensed_ff_pulse.png)
![stop scan A](figures/stop_scan_A.png)
![timeseries A III offset](figures/timeseries_A_III_offset.png)
![timeseries A I near](figures/timeseries_A_I_near.png)
![stop scan A v10](figures/stop_scan_A_v10.png)
![timeseries A v10 III offset](figures/timeseries_A_v10_III_offset.png)
![timeseries A v10 I near](figures/timeseries_A_v10_I_near.png)
![stop scan A v10b](figures/stop_scan_A_v10b.png)
![timeseries A v10b III offset](figures/timeseries_A_v10b_III_offset.png)
![timeseries A v10b I near](figures/timeseries_A_v10b_I_near.png)
![stop scan A v10c](figures/stop_scan_A_v10c.png)
![timeseries A v10c III offset](figures/timeseries_A_v10c_III_offset.png)
![timeseries A v10c I near](figures/timeseries_A_v10c_I_near.png)
![stop scan A2](figures/stop_scan_A2.png)
![timeseries A2 III offset](figures/timeseries_A2_III_offset.png)
![timeseries A2 I near](figures/timeseries_A2_I_near.png)
![stop scan A2 I near screened](figures/stop_scan_A2_I_near_screened.png)
![yaw gate A2 III offset](figures/yaw_gate_A2_III_offset.png)
![stop scan A2 guo I near](figures/stop_scan_A2_guo_I_near.png)
![timeseries A2 guo I near](figures/timeseries_A2_guo_I_near.png)
![stop scan A2 guo v3 I near](figures/stop_scan_A2_guo_v3_I_near.png)
![timeseries A2 guo v3 I near](figures/timeseries_A2_guo_v3_I_near.png)
![typical seed B partial](figures/typical_seed_B_partial.png)
![median scatter B partial](figures/median_scatter_B_partial.png)
![colab seed112 G6 G7 B](figures/colab_seed112_G6_G7_B.png)
![reference gate B3](figures/reference_gate_B3.png)
![timing scan B3](figures/timing_scan_B3.png)
![median scatter B stop](figures/median_scatter_B_stop.png)
![typical seed B stop](figures/typical_seed_B_stop.png)
![yaw vs false stop C](figures/yaw_vs_false_stop_C.png)
![negative load D](figures/negative_load_D.png)
![tradeoff D](figures/tradeoff_D.png)
![negative load D](figures/negative_load_D.png)
![tradeoff D](figures/tradeoff_D.png)

## 目录

- `results/`：结果表与说明
- `reviews/`：多模型审稿人审查后的裁决
- `figures/`：结果图
- `code/`：试验脚本（原样保存，路径已改为相对路径，运行前需按各脚本说明准备数据与环境）
