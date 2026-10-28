# NatHaz AI Lab

风工程 AI 自动科研实验室。

- **Liang Hu** — Principal Investigator
- **Ahsan Kareem** — Advisor
- **Yanlin Guo** — Reviewer


> AI 每天聚合风工程和相近领域的论文和研究进展，然后由本人根据其独特的口味从中精心选择有希望的思路，经由 Agents 实现、检验并探索如何用于 PI 本人的研究领域。
>
> —— Liang Hu

## 研究原则

1. **第一性原理。** 所有研究从第一性原理出发；对风工程而言，这意味着只保留结果真实、可验证、且有应用价值的研究。
2. **应用导向。** 风工程是应用学科，不追逐过于偏向其他学科的研究：例如，只使用大模型，不追求改进大模型。
3. **半自动、人在回路。** 研究基本以半自动方式进行（human-in-the-loop）：Agents 执行与检验，科学品味、鉴赏与批评由 PI 注入。

每个思路开成一个子项目，有四种状态：**探索中**（正在试）、**搁置**（已有结论，暂不继续）、**待转正**（值得做成正式研究，等 PI 决定）、**已转正**（已转成正式项目）。

本仓库收录已告一段落的试验子项目：阶段结论、原始任务、项目报告、审查裁决、结果、图和脚本；过程对话不收录。内容由 AI 自动生成，未经同行评审。

> **说明 / Note**：这些都是**测试性质的探索试验**，"搁置""已转正"只表示该试验告一段落，**不是正式结题**，阶段结论不代表最终研究结论。
> These are **exploratory test trials**. "Shelved" / "Promoted" only mean the trial has paused or moved on; **none is a formally concluded study**, and the interim findings are not final research conclusions.

## 已告一段落的试验子项目 / Trials that have paused

### 实验室（试验场）

| 子项目 | 状态 | 结论 |
|---|---|---|
| [广州城市风场 GPU-LBM（LatticeUrbanWind）复现可行性](projects/latticeurbanwind-guangzhou/) | 已转正 | 10-15 转正为正式项目「城市风场 GPU-LBM（LUW）」；材料已复制到新项目，已确认接收（2564 个文件逐条一致）并归入，先做近壁处理工作包；实验室不再派 LUW 计算、不再跟进 |
| [Strata + Qwen3.8-Flash-Next 本地推理（Colab A100）](projects/strata-qwen-local-inference/) | 搁置 | 能做到：Colab A100 不降档跑通 32K，输出 35–59 tok/s，needle 3/3，约 5 CU；每个新会话约 40 min/4 CU 准备，暂无用例故搁置 |
| 　[文献库全文检索 + 风工程数据抽取](projects/fulltext-kb-data-extraction/) | 已转正 | 10-14 已转正为平台工具 pages：验收五组全过线，二期非首页事实题 22/27 到页；三期盲测 10-14：到页 21/30（中文 9/10、中译英 8/10、书 4/7、扫描书 0/3），书籍偏弱经平台 0062 改进后 round3 书籍到页 4/10→7/10（达标）、round4 8/12 不变；台式机 I 盘已连通并清点：净新增约 1.25 万 PDF/42 万页，第一阶段已抽 28.9 万页有文字页（工作站 1.8 GB）；台式机 41.9 万页重抽版已交、0069 10-15 14:1x 放行入库；10-15 全部推进：剩余 10.5 万页 OCR 10-16 02:38 完成（105,336 页，已交 0069）、三库元数据与作品去重、djvu/pdg 书 31,365 页已交平台（472 页超星格式未解）、litwiki/knowledge 试用已回；入库等 0051 与 C 盘处理。10-13 结论：只做检索。两库 4,691 PDF/12.9 万页本地按页索引；非首页事实题前 5 精确到页约一半（英文 8/14、中文原文 5/5、中文问英文译问题后 3/5、书 4/6）， 论文级 1/27；平台已接入（三期，一期本周内），原型冻结作对照；` pages` 一期已上线（10-13 22:40 实测）；扫描件 OCR 79 份/5,422 页已交二期。廓线抽取搁置（单页文本 6/78 错、27/78 需限定，图页常定位错）；0 CU；另一台电脑上的书待 Liang Hu 给信息 |
| [自建/本地模型对我们研究的用途](projects/own-llm-use-cases/) | 搁置 | 不做自己的语言大模型（继续预训练/全量微调），LoRA 暂不做。评测 200 题摘要初筛：本地 Qwen3-32B 82.0%、Claude Sonnet 80.5%、Gemini 3.8 Flash 85.5%（置信区间重叠）；50 题 PDF 单值抽取：本地 92%、前沿 96%。建议成批筛选/抽取交 Gemini 3.8 Flash 批量通道或 Colab 本地 Qwen3-32B，Claude 只做复核；约 6.8 CU。物理场代理部分另留档搁置 |
### AI 气象 / 气候大模型与风工程

| 子项目 | 状态 | 结论 |
|---|---|---|
| 　[建筑高风速预报与主动控制](projects/a2-building-highwind-forecast-control/) | 搁置 | 小时级预报已被官方预警覆盖；秒级预视只拿到完美收益 0–17%，卡在来流预测 |
| 　[风机高风速预报与调控](projects/a3-wind-turbine-highwind-forecast-control/) | 搁置 | 10-15 分段 D：偏心路径预视停机降偏航力矩约 25%，近中心塔底反向弯矩恶化 14% → 按预定规则搁置；10-16 旧风场 4/4 逐字节一致 |
| 　[复杂地形风预警](projects/e-complex-terrain-wind-warning/) | 搁置 | 瑞士 12 站：物理降尺度在单站订正外无增量 |
| 　[风敏感作业与结构预警](projects/f-wind-sensitive-operations-warning/) | 搁置 | 概率预警的优势来自概率形式，不是 AI 多源 |
| 　[B1+B4 登陆飓风：AI 路径与集合到站点峰值风](projects/b1b4-landfall-hurricane-ai-track-wind/) | 搁置 | 48 h 误差比 1.021 过但事件 5/9 不足；两链都偏低 35–38%，输入假设盖住路径影响 |
| 　[B2 AI 混合合成台风到沿海设计风速](projects/b2-ai-synthetic-tc-design-wind/) | 搁置 | STORM 过闸 0，RAFT 偏低约 31%，主因 RAFT 近岸几乎不出 Cat3+ |
| 　[AI 气象大模型预报用途（强风背景场、风电、CFD）](projects/ai-weather-model-use/) | 搁置 | AI 全球模型对流背景场只到 12–24 h |
| 　[对流尺度AI与雷暴短临](projects/l-convective-scale-ai-nowcast/) | 搁置 | 10-16 审查 ：StormCast V1/CONUS + 常数系数阵风代理按冻结门槛未达扩样标准，暂停该配置；不等于 AI 不如 HRRR（差异不显著、口径敏感）；重启需重新预注册（盲样本、阵风诊断、概率型判据）；约 212 CU；10-16 第三轮预注册经审查 冻结（定稿），S0 已冻结（V1 120 + CONUS 80 个事件，200 个对照），S1 修正后通过（中位比 1.00、r=0.98），合计约 6.4 CU；S2（约 144 CU）待母项目放行 |
| 　[风灾损失与风速数据库](projects/i-loss-wind-database/) | 搁置 | 大模型抽取可用；缺独立风速（雷暴）和跨风速带的带分母逐栋数据（飓风） |
| 　[观测与模拟融合重建风场](projects/h-obs-model-fusion-wind/) | 搁置 | ASOS 站网上融合只比克里金好 0–4%；协议 v1.2 留用；雷暴近地风速当前公开数据不可做 |

## 说明

- 所有试验由 AI 智能体（Claude、GPT、Gemini、Grok、GLM 等）自动完成，结果未经同行评审，可能有错；引用前请核对原始文献与数据。
- 使用的数据、代码与文献见 [CITATIONS.md](CITATIONS.md)。
