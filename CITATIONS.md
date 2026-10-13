# 引用与致谢

本页展示的试验使用了以下公开数据、代码与文献。转引本页内容时请引用原始来源。（由实验室 Lead 维护：新用到外部数据、代码、模型或文献时，在这里补一条。）

## 数据
- **TPU Aerodynamic Database（东京工艺大学风洞气动数据库）**：高层建筑表面风压数据库。Tokyo Polytechnic University, Wind Engineering Research Center. http://www.wind.arch.t-kougei.ac.jp/system/eng/contents/code/tpu
- **UrbanTALES**：城市 LES 风场公开数据集（旧项目 graph-deeponet-wind 使用）。

## 代码与模型
- **LatticeUrbanWind (LUW)**：GPU 格子玻尔兹曼城市风场求解器，https://github.com/hweifluids/LatticeUrbanWind
- **Qwen3.8-Flash-Next**（Qwen 团队）与 **Strata** 推理引擎：Colab A100 本地推理试验。
- **Google Colab**（A100 GPU）：全部 GPU 试验的算力。

## 文献
- Han et al. (2026). 广州城市风场 GPU-LBM 模拟. *Developments in the Built Environment*, 101057. https://doi.org/10.1016/j.dibe.2026.101057；arXiv:2607.04516
- FARS: A Fully Automated Research System Deployed at Scale. arXiv:2606.31651（本页的展示形式参考）

- Tokyo Polytechnic University (TPU) Aerodynamic Database of High-rise Buildings. https://db.wind.arch.t-kougei.ac.jp/aerodynamic/experiment/highrise/ （自建模型用途：风压代理试验数据）
- NOAA NCEI Storm Events Database. https://www.ncei.noaa.gov/stormevents/ （本地 LLM 评测 C 组）
- Qwen Team (2025). Qwen3 模型（Qwen3-8B、Qwen3-30B-A3B-Instruct-2507、Qwen3-32B）. https://huggingface.co/Qwen （本地 LLM 评测）
- Kwon et al. (2023). vLLM: Efficient Memory Management for Large Language Model Serving with PagedAttention. SOSP. https://github.com/vllm-project/vllm
- Ovadia et al. (2023). Fine-Tuning or Retrieval? Comparing Knowledge Injection in LLMs. arXiv:2312.05934
- Balaguer et al. (2024). RAG vs Fine-tuning: Pipelines, Tradeoffs, and a Case Study on Agriculture. arXiv:2401.08406
- Pan et al. (2024). AstroMLab 2: AstroLLaMA-2-70B and Benchmarking Specialised LLMs for Astronomy. arXiv:2409.19750
- Thulke et al. (2024). ClimateGPT. arXiv:2401.09646
- Optimal large language models to screen citations for systematic reviews (2025). Research Synthesis Methods. PMC12657656
- 周颖等 (2025). 土木工程专业知识驱动大语言模型构建与评测体系. 同济大学学报(自然科学版) 53(6):831–840. DOI 10.11908/j.issn.0253-374x.24358
- AIJ (Architectural Institute of Japan) 城市风环境 CFD 验证基准，Case E（新潟市街区风洞试验），https://www.aij.or.jp/jpn/publish/cfdguide/index_e.htm （LUW 复现试验的风洞参照；数据随 LUW 仓库样例提供）
- Lehmann, M. FluidX3D. https://github.com/ProjectPhysX/FluidX3D （LUW 的求解器内核）
- Strata 推理引擎（Niko1221），https://github.com/Niko1221/Strata （v0.1.43）；unsloth Qwen3.8-Flash-Next GGUF 量化（UD-IQ4_XS），https://huggingface.co/unsloth/Qwen3.8-Flash-Next-GGUF

### AI 气象模型预报用途（10-13）
- Hersbach, H. et al. (2020). The ERA5 global reanalysis. *Q. J. R. Meteorol. Soc.* 146, 1999–2049. https://doi.org/10.1002/qj.3803；Copernicus Climate Change Service (C3S) Climate Data Store。本试验经 Google Research ARCO-ERA5 公开 Zarr 读取（Carver & Merose 2023, https://github.com/google-research/arco-era5）
- Bi, K. et al. (2023). Accurate medium-range global weather forecasting with 3D neural networks (Pangu-Weather). *Nature* 619, 533–538. https://doi.org/10.1038/s41586-023-06185-3；权重 CC BY-NC-SA 4.0，https://github.com/198808xc/Pangu-Weather
- Chen, L. et al. (2023). FuXi: a cascade machine learning forecasting system for 15-day global weather forecast. *npj Clim. Atmos. Sci.* 6, 190. https://doi.org/10.1038/s41612-023-00512-1；https://github.com/tpys/FuXi （本试验经 earth2studio 封装取镜像权重，按 CC BY-NC-SA 4.0 非商用处理）
- Lam, R. et al. (2023). Learning skillful medium-range global weather forecasting (GraphCast). *Science* 382, 1416–1421. https://doi.org/10.1126/science.adi2336；https://github.com/google-deepmind/weathernext （本试验未运行；权重许可 2026-08-06 更新为可商用）
- NVIDIA Earth2Studio（v0.19.0，Apache-2.0）. https://github.com/NVIDIA/earth2studio；ECMWF ai-models. https://github.com/ecmwf-lab/ai-models
- May, R. M. et al. MetPy（v1.7.1）. https://github.com/Unidata/MetPy；https://doi.org/10.5065/D6WW7G29
- Feldmann, M., Beucler, T., Gomez, M., Martius, O. (2024). Lightning-fast convective outlooks: predicting severe convective environments with global AI-based weather models. arXiv:2406.09474
- Hua, Z., Hakim, G., Anderson-Frey, A. (2025). *Geophys. Res. Lett.* https://doi.org/10.1029/2024GL109611
- Xu, H. et al. (2024). Pangu-Weather 驱动 WRF 的华北极端降水预报. *Environ. Res. Lett.* https://doi.org/10.1088/1748-9326/ad41f0
- Liu, H.-Y. et al. (2024). AI 全球模型与区域模式结合的台风预报. *JGR: Machine Learning and Computation*. https://doi.org/10.1029/2024JH000207
- DeMaria, M. et al. (2025). AI 全球模型台风路径与强度评估. *AIES*. https://doi.org/10.1175/AIES-D-24-0085.1
- Das, P. et al. (2024). Hybrid physics-AI outperforms numerical weather prediction for extreme precipitation nowcasting. *npj Clim. Atmos. Sci.* 7, 282. https://doi.org/10.1038/s41612-024-00834-8
- Zhang, Y. et al. (2023). Skilful nowcasting of extreme precipitation with NowcastNet. *Nature*. https://doi.org/10.1038/s41586-023-06184-4
- Chen, L. et al. (2025). FuXi-Nowcast. arXiv:2512.08974
- Pathak, J. et al. (2024). StormCast: kilometer-scale convection allowing model emulation. arXiv:2408.10958
- Flora, M. L., Potvin, C. K. (2025). WoFSCast. *Geophys. Res. Lett.* https://doi.org/10.1029/2024GL112383
- Price, I. et al. (2025). Probabilistic weather forecasting with machine learning (GenCast). *Nature*. https://doi.org/10.1038/s41586-024-08252-9
- Hardy, L., Finney, I. (2025). 100 m 轮毂高度风速降尺度. *Meteorol. Appl.* https://doi.org/10.1002/met.70038
- Lin, C. et al. (2026). Reconstructing fine-scale 3D wind fields with terrain-informed machine learning (FuXi-CFD). *Nat. Commun.* https://doi.org/10.1038/s41467-026-70562-5
- Mahesh, A. et al. (2025). Huge ensembles (HENS). *Geosci. Model Dev.* 18, 5575/5605. https://doi.org/10.5194/gmd-18-5575-2025
- Vonich, P. T., Hakim, G. J. Atmospheric predictability beyond 30 days with machine learning. arXiv:2504.20238
- Radford, J. T. et al. (2025). AI weather prediction model reforecasts on AWS. *BAMS*. https://doi.org/10.1175/BAMS-D-24-0057.1；https://registry.opendata.aws/aiwp/
- Matsugishi, S., Satoh, M., Ohno, T. (2026). Resolution dependence in a global atmospheric simulation from km to 220 m grid spacing. *Geophys. Res. Lett.* 53, e2026GL124411. https://doi.org/10.1029/2026GL124411

## 致谢
试验由 AI 智能体（Claude、GPT、Gemini、Grok、GLM 等）自动完成，由 NatHaz 指导。
