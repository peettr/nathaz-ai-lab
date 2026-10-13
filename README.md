# NatHaz AI Lab

风工程 AI 自动科研实验室。

- **Liang Hu** — Principal Investigator
- **Ahsan Kareem** — Supervisor
- **Yanlin Guo** — Reviewer


> AI 每天聚合风工程和相近领域的论文和研究进展，然后由本人根据其独特的口味从中精心选择有希望的思路，经由 Agents 复现、检验并探索如何用于 PI 本人的研究领域。
>
> —— Liang Hu

每个思路开成一个子项目，有四种状态：**探索中**（正在试）、**搁置**（已有结论，暂不继续）、**待转正**（值得做成正式研究，等 PI 决定）、**已转正**（已转成正式项目）。

本仓库收录已有结论的子项目：结论、报告、审查裁决、结果、图和脚本：原始任务、Agents 之间的对话原文、决定、审查和结果。内容由 AI 自动生成，未经同行评审。

## 已有结论的子项目

| 子项目 | 状态 | 结论 |
|---|---|---|
| [Strata + Qwen3.8-Flash-Next 本地推理（Colab A100）](projects/strata-qwen-local-inference/) | 搁置 | 能做到：Colab A100 不降档跑通 32K，输出 35–59 tok/s，needle 3/3，约 5 CU；每个新会话约 40 min/4 CU 准备，暂无用例故搁置 |
| [自建/本地模型对我们研究的用途](projects/own-llm-use-cases/) | 搁置 | 不做自己的语言大模型（继续预训练/全量微调），LoRA 暂不做。评测 200 题摘要初筛：本地 Qwen3-32B 82.0%、Claude Sonnet 80.5%、Gemini 3.8 Flash 85.5%（置信区间重叠）；50 题 PDF 单值抽取：本地 92%、前沿 96%。建议成批筛选/抽取交 Gemini 3.8 Flash 批量通道或 Colab 本地 Qwen3-32B，Claude 只做复核；约 6.8 CU。物理场代理部分另留档搁置 |
| [AI 气象大模型预报用途（强风背景场、风电、CFD）](projects/ai-weather-model-use/) | 搁置 | 10-13：三事件回算，AI 全球模型给对流背景场只到 12–24 h 且不稳定（CAPE 是瓶颈，风切/DCAPE 多好于持续性）；后报用 ERA5 更好；最有希望的是 AI 驱动 WRF（需 WRF 线、正式项目规模）；<11.3 CU |

## 说明

- 所有试验由 AI 智能体（Claude、GPT、Gemini、Grok、GLM 等）自动完成，结果未经同行评审，可能有错；引用前请核对原始文献与数据。
- 使用的数据、代码与文献见 [CITATIONS.md](CITATIONS.md)。
