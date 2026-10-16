# 引用与致谢

本页展示的试验使用了以下公开数据、代码与文献。转引本页内容时请引用原始来源。（由实验室 Lead 维护：新用到外部数据、代码、模型或文献时，在这里补一条。）

- DjVuLibre Project (2026), *DjVuLibre* command-line tools (`djvused`, `djvutxt`, `ddjvu`), https://djvu.sourceforge.net/ （台式机旧书文字层提取、页图本机渲染）。
- Smith, R. (2007), An Overview of the Tesseract OCR Engine, *ICDAR 2007*, https://doi.org/10.1109/ICDAR.2007.4376991；Tesseract OCR 项目 https://github.com/tesseract-ocr/tesseract （台式机旧书本机 OCR，简体中文与英文语言包）。
- mahavivo (2026), *pdg-converter*, MIT 开源代码，https://github.com/mahavivo/pdg-converter （台式机超星 PDG 单页图像解封装；仅部分编码有样本验证，故失败页单列）。

## 数据
- Bauerová, P. et al. (2024), TURDATA: Prague urban air-quality and remote-sensing measurements, Zenodo 10655033, CC BY 4.0, https://doi.org/10.5281/zenodo.10655033 （A1 Prague v1 PVK roof RAW/processed lidar 2022-04—09 逐门 QC 与城区预报检验）。
- OpenStreetMap contributors (2026), Prague PVK 周边建筑轮廓与高度/楼层，Open Database License (ODbL), https://www.openstreetmap.org/copyright （A1 Prague v1 形态学源区；楼层换高度和缺失补值为本线假设）。
- Iowa State University / Iowa Environmental Mesonet (2026), LKPR historical METAR 10 m wind archive, https:/?help= （A1 Prague v1 时钟交叉核对、机场地面 MOS；原始 METAR CSV 不公开转存）。
- Bauerová, P. et al. (2024), Measurement report: TURBAN observation campaign combining street-level low-cost air quality sensors and meteorological profile measurements in Prague, EGUsphere preprint, https://doi.org/10.5194/egusphere-2024-1222 （A1 Prague v1 时钟/仪器高度、方法背景；预印本第 13 页 §2.3）。
- Morrison, W. et al. (2025), Harmonised boundary layer wind profile dataset from six ground-based Doppler wind lidars in a transect across Paris (France), Zenodo L3 v1.42, CC BY 4.0, https://doi.org/10.5281/zenodo.17710093 （A1 巴黎可行性核验及 PALUPD 111/161 m 预报评分、第三步 PAARBO/PACHEM 迁移；公开 600 s NetCDF，CC BY 4.0）。论文：*Earth System Science Data* 17, 6507–6529, https://doi.org/10.5194/essd-17-6507-2025。
- Iowa State University / Iowa Environmental Mesonet (2026), 巴黎 LFPO/LFPB/LFPG METAR 历史存档，https://mesonet.agron.iastate.edu/request/download.phtml?network=FR__ASOS; API https:/?help= （A1 第三步 LFPO 地面风跨场地 MOS；公开下载，IEM 页面未注明统一再许可条款，原始机场 CSV 不作为发布物）。
- Institut national de l'information géographique et forestière (IGN, 2026), BD TOPO® V3 Bâtiment footprint/hauteur, Licence Ouverte 2.0, https://www.data.gouv.fr/datasets/bd-topo-r; WFS https://data.geopf.fr/wfs/ows; field documentation https://bdtopoexplorer.ign.fr/batiment （A1 第四步 PALUPD 2 km 建筑形态；现版地图用于 2023–24 回溯，存在时序错配）。
- World Meteorological Organization (2023), *Guide to Instruments and Methods of Observation*, Vol. III, Ch. 9 Urban Observations, https://amc.namem.gov.mn/wp-content/uploads/WMO/1.%208_III-2023_en.pdf （A1 巴黎城市廓线方法背景；本试验 z0/幂律指数为假设，非 WMO 指定本站参数）。
- **TPU Aerodynamic Database（东京工艺大学风洞气动数据库）**：高层建筑表面风压数据库。Tokyo Polytechnic University, Wind Engineering Research Center. http://www.wind.arch.t-kougei.ac.jp/system/eng/contents/code/tpu
- **UrbanTALES**：Nazarian, N., Lu, J., Lipson, M. J., Hart, M. A., Liu, S., Krayenhoff, E. S., Blunn, L., & Martilli, A. (2025). UrbanTALES: A Large-Eddy Simulation Dataset for Urban Canopy Layer Turbulence and Parameterization. *Bulletin of the American Meteorological Society* 106(12), E2461–E2478. https://doi.org/10.1175/BAMS-D-25-0061.1；数据 https://urbantales.vercel.app/ （网站标 CC BY-NC 4.0，非商业）。本试验仅读旧项目 CRC 副本；卡片。
- **Lu et al. 2025**：Lu, J., Li, W., Hobeichi, S., Azad, S. A., & Nazarian, N. (2025). *Environmental Research Letters* 20, 054006. https://doi.org/10.1088/1748-9326/adc148 （UrbanTALES 行人风 U-Net 先例，J 子项目对照）。
- **Lumet et al. 2025**：Lumet, E., Rochoux, M. C., Jaravel, T., & Lacroix, S. (2025). *Building and Environment* 267, 112287. https://doi.org/10.1016/j.buildenv.2024.112287 （LES 代理固定测试集学习曲线设计先例）。

- Oklahoma Mesonet / Oklahoma Climatological Survey (2026), Mesonet Data Files and Data Access and Pricing, https://www.mesonet.org/past-data/mesonet-resources/mesonet-data-files; https://www.mesonet.org/about/data-access-and-pricing （A1 仅核验样例和条款；未发布受限观测序列）。
- NOAA/NCEP (2026), Global Forecast System (GFS) AWS Open Data, https://registry.opendata.aws/noaa-gfs-bdp-pds/ （A1 旧轮仅核验目录；ASOS 新轮使用 2023 业务预报 .idx 范围请求，见）。
- NOAA NCEI (2005–), DSI 6405_02, 1-Minute Page 1 Surface Weather Observations from ASOS Network, https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc:C00386 （A1 ASOS 观测，经 Iowa Environmental Mesonet 解析接口）。
- Iowa State University / Iowa Environmental Mesonet (2026), ASOS 1-Minute Data Download & archived METAR API, https://mesonet.agron.iastate.edu/request/asos/1min.phtml; https:/?help= （A1 数据中转/站点元数据）。

- NOAA National Hurricane Center (2026), HURDAT2 Atlantic best track (1851–2025, 2026-09-23 release), https:/ （B1+B4 事件及最佳路径）。
- NOAA National Hurricane Center (2020–2024), ATCF post-season a-/b-decks, https://ftp.nhc.noaa.gov/atcf/archive/ （B1+B4 官方预报与 RMW/POCI）。
- CIRA/NOAA/NESDIS/STAR (2026), TC Real-Time AI model track product descriptions, https://rammb-data.cira.colostate.edu/tc_realtime/about.asp （B1+B4 s2 NPNG/NGRP/NFOR 来源核查，非已取得历史文件）。
- Google DeepMind/Google Research (2026), Weather Lab: WeatherNext Cyclones experimental cyclone forecast downloads, https://developers.google.com/weathernext/guides/weatherlab （B1+B4 s2 (c′) 文件可用性核查；历史许可 CC BY 4.0，具体风暴文件未取得）。
- Atkinson, G. D. & Holliday, C. R. (1977), Tropical cyclone minimum sea level pressure/maximum sustained wind relationship for the western North Pacific, *MWR* 105:421–427, https://doi.org/10.1175/1520-0493(1977)105%3C0421:TCMSLP%3E2.0.CO;2 （B1+B4 s2 风压幂指数借鉴，实际大西洋缩放为假设）。
- Knaff, J. A. & Zehr, R. M. (2007), Reexamination of Tropical Cyclone Wind–Pressure Relationships, https://ramsdis.cira.colostate.edu/rammb/resources/docs/Knaff_preswind.v4.pdf （B1+B4 s2 对 AH77 关系适用局限的复核；B1 v2c 再核原文 V500 环带但未见指定 850 hPa 层）。
- Knaff, J. A., Longmore, S. P., & Molenar, D. A. (2014), An Objective Satellite-Based Tropical Cyclone Size Climatology, *Journal of Climate* 27, 455–476, https://doi.org/10.1175/JCLI-D-13-00096.1 （B1 v2c 850 hPa V500 层次的后续同系列文献依据，期刊第 455 页摘要；不冒充 Knaff–Zehr 2007 原文）。
- Knaff, J. A., Sampson, C. R., DeMaria, M., Marchok, T. P., Gross, J. M., & McAdie, C. J. (2007), Statistical Tropical Cyclone Wind Radii Prediction Using Climatology and Persistence, *Weather and Forecasting* 22, 781–791, https://doi.org/10.1175/WAF1026.1 （B1 v2 尺度输入方法线索；x 为 Rankine 幂指数，非 Holland B）。
- NOAA/NHC (2026), Isaias 2026-10-09 业务登陆公告及 2026 季 ATCF b-deck / a-deck（暂定路径，非 HURDAT2 最终版）, https://www.nhc.noaa.gov/archive/2026/al09/al092026.update.10100129.shtml; https://ftp.nhc.noaa.gov/atcf/btk/; https://ftp.nhc.noaa.gov/atcf/aid_public/ （B1 v2b 本土登陆与同起报官方链可得性核验）。
- CIRA/NOAA (2022), Extended Best Track v3.0.2（只至 2021；B1+B4 取数核验；B2 输入诊断使用 1988–2018 年 RMW 与陆地距离，按风暴 ID/UTC 匹配 HURDAT2）, https://rammb2.cira.colostate.edu/research/tropical-cyclones/tc_extended_best_track_dataset/；格式与多来源 RMW 说明 https:/。
- Iowa Environmental Mesonet / NCEI (2026), ASOS 1-minute archive and metadata, https://mesonet.agron.iastate.edu/request/asos/1min.phtml; https:/?help （B1+B4 站点试验；与上文 A1 来源相同）。

## 代码与模型
- Holland (1980), An Analytic Model of the Wind and Pressure Profiles in Hurricanes, *Monthly Weather Review* 108, 1212–1218, https://doi.org/10.1175/1520-0493(1980)108%3C1212:AAMOTW%3E2.0.CO;2 （B1+B4 简化筛选公式，非完整边界层）。
- Vickery, Wadhera, Powell & Chen (2009), A Hurricane Boundary Layer and Wind Field Model for Use in Engineering Applications, *JAMC* 48, 381–405, https://doi.org/10.1175/2008JAMC1841.1 （B1+B4 模型对照/未实现完整模型）。
- CLIMADA contributors (2026). CLIMADA Python v6.1.0, GPL-3.0, https://github.com/CLIMADA-project/climada_python/tree/v6.1.0 （B1+B4 H08 风场与平移非对称，固定 commit bb9595944fcf673152ea53e61efbafeb0b1e4406）。
- Natural Earth (2026). 1:10m Physical Vectors: Land, public domain, https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-land/ （B1+B4 风向陆海暴露）。
- Vickery, P. J. & Skerlj, P. F. (2005). Hurricane Gust Factors Revisited, *J. Structural Engineering* 131(5), 825–832. https://doi.org/10.1061/(ASCE)0733-9445(2005)131:5(825) （B1+B4 时距/暴露候选依据，非统一因子；Zotero key ZR7S3SEJ）。
- Krayer, W. R. & Marshall, R. D. (1992). Gust Factors Applied to Hurricane Winds, *BAMS* 73, 613–617. https://doi.org/10.1175/1520-0477(1992)073%3C0613:GFATHW%3E2.0.CO;2 （B1+B4 约2s/10min 因子限制，非直接用于 ASOS）。
- Wang et al. (2020), An Efficient Method for Simulating Typhoon Waves Based on a Modified Holland Vortex Model, *J. Mar. Sci. Eng.* 8, 177, https://doi.org/10.3390/jmse8030177 （B1+B4 H80 梯度风公式查证）。
- **LatticeUrbanWind (LUW)**：GPU 格子玻尔兹曼城市风场求解器，https://github.com/hweifluids/LatticeUrbanWind
- **Qwen3.8-Flash-Next**（Qwen 团队）与 **Strata** 推理引擎：Colab A100 本地推理试验。
- **Google Colab**（A100 GPU）：全部 GPU 试验的算力。

- **Zotero**（Corporation for Digital Scholarship，论文管理与本地 PDF，2026）：https://www.zotero.org/；本试验只读本地附件与元数据。
- **Poppler pdftotext**（The Poppler Developers，PDF 按物理页抽文本）：https://poppler.freedesktop.org/
- **SQLite FTS5**（SQLite Consortium，BM25 全文索引）：https://www.sqlite.org/fts5.html
- **BAAI/bge-small-en-v1.5**（BAAI，2023，CPU 句向量模型）：https://huggingface.co/BAAI/bge-small-en-v1.5
- **FastEmbed**（Qdrant，ONNX 向量推理）：https://github.com/qdrant/fastembed
- **paraphrase-multilingual-MiniLM-L12-v2**（Reimers & Gurevych / sentence-transformers，2020，多语言句向量，CPU 局部候选重排）：https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
- **Gemini 3.8 Flash**（Google，订阅批量单页文本抽取）：https://gemini.google.com/
- **EndNote**（Clarivate，博士文献库 PDF 附件与文件名；2026，本轮仅本机只读）：https://endnote.com/
- **SQLite FTS5 trigram tokenizer**（SQLite Consortium，中文字符三元组本机索引；非外部翻译模型）：https://www.sqlite.org/fts5.html#the_trigram_tokenizer

## 文献
- Päschke, E., Leinweber, R., & Lehmann, V. (2015). An assessment of the performance of a 1.5 μm Doppler lidar for operational vertical wind profiling based on a 1-year trial. *Atmospheric Measurement Techniques* 8, 2251–2266. https://doi.org/10.5194/amt-8-2251-2015 （A1 Prague v1 RAW intensity=SNR+1，文中仪器建议阈值 1.015；本次仅样例门检，非完整 VAD 质量认证）。
- Blocken, B. (2018). LES over RANS in building simulation for outdoor and indoor applications: A foregone conclusion? *Building Simulation* 11, 821–870. https://doi.org/10.1007/s12273-018-0459-3 （A1 巴黎形态高度换算 v3：文中转述 Verkaik 2006 的 60 m blending height；本站取 60 m 仍是假设，100/200 m 作敏感性。不要误引为 Blocken et al. 2016 的期刊第 74 页。）
- Macdonald, R. W., Griffiths, R. F., & Hall, D. J. (1998). An improved method for the estimation of surface roughness of obstacle arrays. *Atmospheric Environment* 32, 1857–1864. https://doi.org/10.1016/S1352-2310(97)00403-2 （A1 第四步形态学 z0、d，原文印刷 p.1861 式 22–23）。
- Grimmond, C. S. B., & Oke, T. R. (1999). Aerodynamic properties of urban areas derived from analysis of surface form. *Journal of Applied Meteorology* 38, 1262–1292. https://doi.org/10.1175/1520-0450(1999)038%3C1262:APOUAD%3E2.0.CO;2 （A1 第四步形态法范围/限制对照，印刷 pp.1275–1276、1283）。
- Hayakawa, A. (2023). Conversion of Wind Speeds to Various Averaging Times Based on 176 Codes and Standards for Wind-resistant Design of Buildings. *Journal of Wind Engineering (JAWE)* 48(3), PDF 第 1–2 页。https://www.jstage.jst.go.jp/article/jwe/48/3/48_1/_pdf/-char/en （A1×C2 峰值因子/平均时距概念参考；g=3 并非该文对本场景的实测指定值。）
- Kaimal, J. C., & Finnigan, J. J. (1994). *Atmospheric Boundary Layer Flows: Their Structure and Measurement*. 本机 Zotero key `6EZT6DGI`，本试验 PDF 物理页70；馆藏入口：https://search.worldcat.org/search?q=Atmospheric+Boundary+Layer+Flows+Kaimal+Finnigan
- Naudascher, E., & Rockwell, D. (1994). *Flow-Induced Vibrations: An Engineering Guide*. 本机 Zotero key `8AUYKNGT`，PDF 物理页80；馆藏入口：https://search.worldcat.org/search?q=Flow-Induced+Vibrations+Engineering+Guide+Naudascher
- Haltiner, G. J., & Martin, F. L. (1957). *Dynamical and Physical Meteorology*. 本机 Zotero key `Y8V97HH7`，PDF 物理页59；馆藏入口：https://search.worldcat.org/search?q=Dynamical+and+Physical+Meteorology+Haltiner+Martin
- 瞿伟廉、吉柏锋（2013）。《下击暴流的形成与扩散及其对输电线塔的灾害作用》。本机 Zotero key `QFMHI96N`，PDF 物理页23；无可核实在线 DOI。
- 本轮 Zotero 下击暴流单页样本共 37 篇的逐条标题、年份、Zotero key、DOI（有则给 https://doi.org/…）与 PDF 物理页，见；无 DOI 的记录明确留空。
- Romanic, D. (2021). Mean flow and turbulence characteristics of a nocturnal downburst recorded on a 213 m tall meteorological tower. *Journal of the Atmospheric Sciences*. https://doi.org/10.1175/jas-d-21-0040.1 （本轮实测廓线补样本，PDF 物理页17 Fig.16）。
- Romanic, D., Taszarek, M., & Brooks, H. (2022). Convective environments leading to microburst, macroburst and downburst events across the United States. *Weather and Climate Extremes* 37, 100474. https://doi.org/10.1016/j.wace.2022.100474 （I 配对足迹尺度，摘要/期刊第 1 页：微下击暴流损伤风水平尺度小于 4 km）。
- NOAA (JetStream). Thunderstorm Hazards - Damaging Wind, https://www.noaa.gov/jetstream/wind_damage （I 足迹尺度：downburst 至 10 km、microburst 直径小于 4 km；网页无页码）。
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
- NVIDIA Earth2Studio（v0.19.0，Apache-2.0）. https://github.com/NVIDIA/earth2studio；本次 K v2.1 Pangu6 ONNX 镜像 https://huggingface.co/NickGeneva/earth_ai/tree/main/pangu （原 Pangu 权重按 CC BY-NC-SA 4.0 非商用处理）；ECMWF ai-models. https://github.com/ecmwf-lab/ai-models
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

- Architectural Institute of Japan (AIJ). Guidebook for CFD Predictions of Urban Wind Environment — benchmark database, Test Case E (Niigata). https://www.aij.or.jp/jpn/publish/cfdguide/index_e.htm
- Tominaga, Y. et al. (2008). AIJ guidelines for practical applications of CFD to pedestrian wind environment around buildings. *J. Wind Eng. Ind. Aerodyn.* 96, 1749–1761. https://doi.org/10.1016/j.jweia.2008.02.058
- Tominaga, Y., Yoshie, R., Mochida, A., Kataoka, H., Harimoto, K., Nozu, T. Cross comparisons of CFD prediction for wind environment at pedestrian level around buildings, Part 2 (AIJ 公开 PDF C05_5).
- Han, S., Wei, H. et al. (2026). Near-real-time, meter-scale 3D urban wind modeling … GPU-accelerated lattice Boltzmann framework. *Developments in the Built Environment*. https://doi.org/10.1016/j.dibe.2026.101057；代码 LatticeUrbanWind https://github.com/hweifluids/LatticeUrbanWind

## A1 低空/无人机风预报（10-14）
- Bremnes, J. B., Nipen, T. N., & Seierstad, I. A. (2024). Evaluation of forecasts by a global data-driven weather model with and without probabilistic post-processing at Norwegian stations. Nonlinear Processes in Geophysics, 31, 247–257. https://doi.org/10.5194/npg-31-247-2024
- Chen, S. et al. (2026). A Station-Based Evaluation of Machine Learning-based Weather Forecasting Models in Northern Norway. arXiv:2609.10564. https://arxiv.org/abs/2609.10564

### AI 气候模拟器近地风初检（10-14）
- Weyn, J. A. et al. (2025). ACE2: accurately learning subseasonal to decadal atmospheric variability and forced responses. *npj Climate and Atmospheric Science* 8, 205. https://doi.org/10.1038/s41612-025-01090-0；代码 https://github.com/ai2cm/ace；ACE2-ERA5 权重、历史 forcing https://huggingface.co/allenai/ACE2-ERA5
- Kochkov, D. et al. (2024). Neural general circulation models for weather and climate. *Nature*. https://doi.org/10.1038/s41586-024-07744-y；代码 https://github.com/neuralgcm/neuralgcm；公开模拟数据 https://neuralgcm.readthedocs.io/en/latest/neuralgcm_datasets.html
- Couairon, G. et al. (2026). ArchesWeatherGen: Skillful and compute-efficient probabilistic weather forecasting with machine learning. *Science Advances* 12, eadx2372. https://doi.org/10.1126/sciadv.adx2372；代码 https://github.com/INRIA/geoarches
- Cresswell-Clay, N. et al. (2025). A Deep Learning Earth System Model for Efficient Simulation of the Observed Climate. *AGU Advances*. https://doi.org/10.1029/2025AV001706；代码 https://github.com/AtmosSci-DLESM/DLESyM；权重 https://huggingface.co/nvidia/dlesym-v1-era5
- Brenowitz, N. D. et al. (2025). Climate in a Bottle: Towards a Generative Foundation Model for the Kilometer-Scale Global Atmosphere. arXiv:2505.06474. https://arxiv.org/abs/2505.06474；代码 https://github.com/NVlabs/cBottle；权重 https://huggingface.co/nvidia/cbottle
- Rasp, S. et al. (2024). WeatherBench 2: A benchmark for the next generation of data-driven global weather models. arXiv:2308.15560. https://arxiv.org/abs/2308.15560；ERA5 1.5°、6 h 保守重网格化数据集 https://weatherbench2.readthedocs.io/en/latest/data-guide.html。ERA5 原始来源：Hersbach 等 (2020)，见本页第 49 行。
- Rasp, S. et al. (2024), WeatherBench 2 数据指南 https://weatherbench2.readthedocs.io/en/latest/data-guide.html；本轮正式格点对照改用公开的 0.25°、6 h 原网格，直接将 10 m U/V 面积保守重网格至 ACE2 格，不先经 1.5°；ERA5 原始来源 Hersbach 等 (2020)，https://doi.org/10.1002/qj.3803。
- Iowa Environmental Mesonet (Iowa State University). ASOS 网络站点 GeoJSON 元数据，https://mesonet.agron.iastate.edu/geojson/network/IL_ASOS.geojson （站点地图元数据，非风速观测数据）。

- Paciorek, C. J. & Cooley, D. (2026). Quantifying Very Extreme Precipitation and Temperature Using Huge Ensembles Generated by Machine Learning-Based Climate Model Emulators. *BAMS* 107, E1053–E1070. https://doi.org/10.1175/BAMS-D-25-0178.1；复现代码 https://github.com/paciorek/huge-ensemble-eva （AI 气候模拟器万年集合可用性核查）。
- Clark, S. et al. (2026). Disentangling the effects of sea surface temperature and CO2 in global machine learned weather-climate emulators. arXiv:2606.07928. https://arxiv.org/abs/2606.07928；随机权重 https://huggingface.co/allenai/ACE2S-SHiELD-plus，确定性配对权重 https://huggingface.co/allenai/ACE2-SHiELD （AI 气候模拟器随机对照）。
- Kwa, A. et al. (2026). Extreme events and statistics in an AI emulator of a global storm-resolving model. arXiv:2610.17693. https://arxiv.org/abs/2610.17693；模型 https://huggingface.co/allenai/HiRO-ACEv2 （随机高分辨率候选核查，参考目标为 X-SHiELD 而非 ERA5）。
- ECMWF (2016). *IFS Documentation Cy41r2, Part IV: Physical Processes*, §3.10.2, PDF 物理页 52–53, https://www.ecmwf.int/sites/default/files/elibrary/2016/79697-ifs-documentation-cy41r2-part-iv-physical-processes_1.pdf （ERA5 10 m 风开阔地暴露订正原理）；ECMWF (2026), *Forecast User Guide* §9.3, https://confluence.ecmwf.int/spaces/FUG/pages/673551686/Section+9.3+Surface+wind。
- Rucker, K., Baxter, I., Hassanzadeh, P., Shaw, T. A., & Pahlavan, H. A. (2025). *Benchmarking Regional Thermodynamic Trends in an AI emulator, ACE2, and a hybrid model, NeuralGCM*. arXiv:2511.00274v2. https://arxiv.org/pdf/2511.00274v2 （ACE2 37 成员先例；评估热极端与干燥，非 10 m 风极值）。
- Sun, Y. Q., Hassanzadeh, P., Zand, M., Chattopadhyay, A., Weare, J., & Abbot, D. S. (2025). Can AI weather models predict out-of-distribution gray swan tropical cyclones? *PNAS* 122(21). https://doi.org/10.1073/pnas.2420914122 （FourCastNet 灰天鹅热带气旋外推；非 ACE2 10 m 风极值）。
- Guan, H. et al. (2025). *LUCIE: A lightweight uncoupled climate emulator with long-term stability and physical consistency*. arXiv:2405.16297v3. https://arxiv.org/pdf/2405.16297v3 （§4.4/图11 极值：模式 σ=0.34 层风等预报量；非诊断 10 m 风）。

### 对流尺度 AI 地面强风试验（10-14）
- NVIDIA (2024). StormCast V1 模型卡、Apache-2.0 权重与训练时段. https://huggingface.co/nvidia/stormcast-v1-era5-hrrr
- NVIDIA (2026). StormCast-CONUS 模型卡、OpenMDW-1.1 权重与训练时段. https://huggingface.co/nvidia/stormcast-conus
- NVIDIA (2026). Earth2Studio StormCast / CorrDiff ERA5-HRRR 源码（Apache-2.0）. https://github.com/NVIDIA/earth2studio
- NOAA NSSL (2025). WoFSCast 源码（Apache-2.0）. https://github.com/NOAA-National-Severe-Storms-Laboratory/frdd-wofs-cast; Flora & Potvin (2025), https://doi.org/10.1029/2024GL112383
- Chen et al. (2026). FuXi-Nowcast, arXiv:2512.08974v2；Zhu (2026) Zenodo 代码包. https://arxiv.org/abs/2512.08974; https://doi.org/10.5281/zenodo.19911638
- NOAA NCEI (2026 年发布版本). Storm Events 2022–2026 年度事件 CSV 与 IGRA2 探空站清单；对流尺度 AI 第二轮从候选中与 IEM METAR/PK WND 核对了 2023 年 23 例和 2026 年 12 例，实际集合试验仅完成其中 2023 年 2 例、2026 年 1 例；无事件对照尚仅为候选。 https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/; https:/
- Iowa Environmental Mesonet (2026). 历史 ASOS/METAR 与探空资料接口. https:/?help=; https:/?help=
- NOAA (2026). AWS 公共 HRRR 分析与预报归档（Earth2Studio 取数）. https://registry.opendata.aws/noaa-hrrr-pds/
- NOAA NCEI / Iowa State University IEM (2026). ASOS 归档 1 分钟资料（`gust_sknt`，5 秒阵风；已经过站内实时质控，并非未质控传感器原始数据）. https://mesonet.agron.iastate.edu/request/asos/1min.phtml; https:/?help=
- Cook, N. J. (2023). Impact of ASOS Real-Time Quality Control on Convective Gust Extremes in the USA. *Meteorology* 2(2), 276–294. https://doi.org/10.3390/meteorology2020017 （2014 年前 ASOS 对流阵风事件模拟 Test 10 后约 10% 的峰值被删；不可作为所有 ASOS 事件的普遍缺失率，已删值不可从 IEM 归档恢复；期刊页码经 Crossref 核为 276–294）。
- Abdi, D., Jankov, I., Madden, P., Vargas, V., Smith, T. A., Frolov, S., Flora, M., & Potvin, C. (2025). HRRRCast: a data-driven emulator for regional weather forecasting at convection allowing scales. arXiv:2507.05658, §数据集训练 2021-03 至 2024-03. https://arxiv.org/abs/2507.05658; NOAA-GSL (2026), HRRRCast-live 代码/公开 Git LFS 权重（仓库 MIT，权重未见独立许可声明）, https://github.com/NOAA-GSL/HRRRCast-live; NOAA GSL 模型页 https://gsl.noaa.gov/hrrrcast/ （本轮在 Colab 完整下载并核对权重 SHA256，TensorFlow 2.15 CPU 成功载入；尚未完成事件推理；6 km，默认层顶 200 hPa）。
- Collins, E. et al. (2024). Forecasting High Wind Events in the HRRR Model over Wyoming and Colorado. Part I: Evaluation of Wind Speeds and Gusts. *Weather and Forecasting* 39, 705–723. https://doi.org/10.1175/WAF-D-23-0036.1 （冷季复杂地形样本 HRRR 大风低估；不可移植数值偏差至本轮暖季雷暴）。
- Kansas State University Weather Data Library / Kansas Mesonet (2026). Historical five-minute station wind maximum (`WSPD10MMAX`, m/s), station metadata and REST variable definitions; CNK 无事件对照独立站网核查，不公开原始逐时序列。https://mesonet.k-state.edu/rest/; https://mesonet.k-state.edu/rest/stationnames/; https://mesonet.k-state.edu/rest/variables/

### K Akron WPS 驱动来源预检（10-14）
- NOAA/NCEP/NCEI (2020), GFS 0.5° analysis/forecast archive, https://www.ncei.noaa.gov/products/weather-climate-models/global-forecast （K 所需 2020 年原生 0.5° 在线文件尚未取得）。
- NSF NCAR GDEX / NOAA NCEP (2020), GFS 0.25 Degree Analysis and Forecast Grids Historical Archive d084001, https://gdex.ucar.edu/datasets/d084001/; DOI https://doi.org/10.5065/D65D8PWK （K v2.1 G/P 起报、G 预报与两组共用陆面场的实际数据源；B1 v2c 2020 年三例 GFS 匿名实读；原生 0.25°）。
- NOAA/NCEP NCO (2026), Current Status of NCEP Model Production, https://www.nco.ncep.noaa.gov/pmb/nwprod/prodstat （B1 v2c GFS 产品 48 h 发布时间保守规则；滚动 30 天平均，非历史逐案发布时间）。
- NOAA/NWS ASOS Program (2025), ASOS Sites by Equipment and Wind Tower Height, https://www.weather.gov/asos/asosequip.html; https://www.weather.gov/media/asos/ASOS%20Sites%20by%20Equipment%20As%20Of%203_18_2025.xlsx （B1 v2c 逐站 2025 设备快照核验；不能证明 2020–24 事发时高度）。
- NOAA/NCEI, Historical Observing Metadata Repository (HOMR) API, https://www.ncei.noaa.gov/access/homr/api （B1 v2c 历史站点元数据查证入口；未把 2025 快照冒充历史证明）。
- Brewer, Fovell & Capps (2025), GraphCast-WRF coupling, *Weather and Forecasting*, https://doi.org/10.1175/WAF-D-24-0097.1; 配套代码与 Vtable（Apache-2.0）https://github.com/rfovell/GraphCast-WRF （K 土壤/地面字段做法预检）。
- Deng et al. (2025), Impacts of lateral boundary conditions from numerical models and data-driven networks on convective-scale ensemble forecasts, *Atmospheric and Oceanic Science Letters*, https://doi.org/10.1016/j.aosl.2025.100589 （K 层数对照出处；未以此推断地面场）。
- NCAR MMM / WRF Users Guide, WPS Intermediate File Format, https://www2.mmm.ucar.edu/wrf/OnLineTutorial/Basics/IM_files/IM_wps.php （K v2.1 中间格式 v5 记录结构、字段层级与投影定义）。
- Unidata / UCAR, THREDDS NetCDF Subset Service, https://www.unidata.ucar.edu/software/tds/current/reference/NetcdfSubsetServiceReference.html （K v2.1 在 Colab 上按变量与区域提取 GDEX GRIB2）。

## 致谢
试验由 AI 智能体（Claude、GPT、Gemini、Grok、GLM 等）自动完成，由 NatHaz 指导。
- NOAA NCEI, Storm Data Bulk Data Format（Storm Events 批量 CSV 字段说明），https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/Storm-Data-Bulk-csv-Format.pdf （I 损失–风速库：magnitude_type 定义）。

### H 站点留一重建 r1（10-14）
- Iowa State University / Iowa Environmental Mesonet (2026), TX_ASOS station GeoJSON and archived METAR, https:/?network=TX_ASOS; https://mesonet.agron.iastate.edu/request/download.phtml?network=TX_ASOS （H 站点元数据、2020–21 小时风，非一分种资料）。
- Hersbach et al. (2020), ERA5 reanalysis, https://doi.org/10.1002/qj.3803; Google Research (2023–), ARCO-ERA5 public Zarr, https://github.com/google-research/arco-era5 （H 10 m U/V 背景场）。
- NOAA/NCEP (2020–21), HRRR f01 public AWS archive, https://registry.opendata.aws/noaa-hrrr-pds/; Blaylock et al., Herbie HRRR inventory reference, https://herbie.readthedocs.io/en/stable/user_guide/tutorial/inventory.html （H 10 m U/V 范围请求）。
- NOAA NCEI (2026 archive), Storm Events Database 2020/21 bulk details, https://www.ncei.noaa.gov/access/storm-events-database/bulk-data （H 雷暴大风排除）。
- NOAA NCEI (2026 archive), Storm Events Database 2018–2024 年度 details CSV, https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/ （H3 温带气旋候选 High Wind/Thunderstorm Wind 逐日筛选；报告县/预报区未必代表全区域无局地对流）。

### A3 风机预视控制（10-14）
- NREL / OpenFAST contributors (2026). OpenFAST v5.0.0（Apache-2.0）. https://github.com/OpenFAST/openfast （A3 本地风机气弹仿真）。
- Abbas et al. (2021). ROSCO: A Reference Open-Source Controller, https://doi.org/10.5194/wes-2021-19; ROSCO v2.10.6（Apache-2.0）https://github.com/NatLabRockies/ROSCO （A3 反馈控制器与 NREL 5 MW 例）。
- Jonkman et al. (2009). Definition of a 5-MW Reference Wind Turbine, NREL/TP-500-38060 （A3 风机模型）。
- Guo, Schlipf & Cheng (2023). WES 8:149–171, https://doi.org/10.5194/wes-8-149-2023; MSCA-LIKE Baseline-Lidar-assisted-Controller（MIT）https://github.com/MSCA-LIKE/Baseline-Lidar-assisted-Controller （A3 激光雷达前馈链参考）。
- Nguyen (2012). The influence of thunderstorm downbursts on wind turbine design, PhD thesis, UT Austin; Nguyen & Manuel (2014), Energies 7:6527, https://doi.org/10.3390/en7106527 （A3 下击暴流入流模型）。
- Cai, Y. et al. (2026). Diffusion posterior sampling enables zero shot kilometre scale wind forecasting over complex terrain (KiloGen). arXiv:2607.21460 （E 节点文献）。
- Seto, D. et al. (2025). Evaluation of HRRR wind speed forecast and WindNinja downscaling accuracy during Santa Ana wind events in Southern California. *Weather and Forecasting* 40:525–541. https://research.fs.usda.gov/treesearch/69198 （E 节点文献）。
- Wagenbrenner, N. S. et al. (2016). Downscaling surface wind predictions from NWP models in complex terrain with WindNinja. *ACP* 16:5229–5245. https://doi.org/10.5194/acp-16-5229-2016；WindNinja（USFS Missoula Fire Sciences Lab，公有领域）https://github.com/firelab/windninja （E 节点降尺度工具）。
- Lin, C. et al. (2025). Terrain-aware Deep Learning for Wind Energy Applications (FuXi-CFD). arXiv:2505.12732；ONNX 权重（CC BY-NC 4.0，第三方转载）https://github.com/tyxackr/FuXi-CFD （E 节点降尺度工具）。
- MeteoSwiss SwissMetNet 自动站开放数据（10 分钟风速与阵风），Source: MeteoSwiss. https://opendatadocs.meteoswiss.ch/a-data-groundbased/a1-automatic-weather-stations （E 节点观测）。
- NASA/USGS SRTM 30 m DEM, https://doi.org/10.5066/F7PR7TFT （E 节点地形）。
- ESA WorldCover Consortium (2022). ESA WorldCover 2021 v200. https://doi.org/10.5281/zenodo.7254221；经 Microsoft Planetary Computer `esa-worldcover` STAC 读取（H 观测–模拟融合 r1 下垫面分组）。
- NOAA/NWS, ASOS Wind Sensor 说明, https://www.weather.gov/asos/WindSensor.html （H r1 风速口径）。
- H2 登陆飓风站点留一（2026）：Iowa Environmental Mesonet TX/LA/MS/AL/FL/GA_ASOS 站点 GeoJSON 与小时 METAR（https://mesonet.agron.iastate.edu/geojson/network/FL_ASOS.geojson; https:/?help=）；NHC HURDAT2 与 ATCF b-deck（https://www.nhc.noaa.gov/data/hurdat/; https://ftp.nhc.noaa.gov/atcf/archive/）；Google Research ARCO-ERA5 10 m U/V（https://github.com/google-research/arco-era5）；CLIMADA v6.1.0 H08 与 Natural Earth 陆地多边形（https://github.com/CLIMADA-project/climada_python/tree/v6.1.0; https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-land/）。为本页上述原始数据/代码的复用，非新数据产品。
- Brewer, M. J., Fovell, R. G., Capps, S. B. (2025). Hybrid NWP: Downscaling GraphCast AI forecasts for downslope windstorms. *WAF* 40:187–206. https://doi.org/10.1175/WAF-D-24-0097.1 （E 节点文献）。
- Wu, Y., Wang, Z., Wang, N. (2026). From AI weather prediction to infrastructure resilience (ACDF). arXiv:2603.12828 （E 节点文献）。
- Le Toumelin, L. et al. (2023) *AIES* https://doi.org/10.1175/AIES-D-22-0034.1；(2024) *NPG* 31:75–97 https://doi.org/10.5194/npg-31-75-2024 （DEVINE，E 节点文献）。
- FuXi-CFD 官方代码与权重（CC BY-NC 4.0）：Zenodo https://doi.org/10.5281/zenodo.18770845 （E 节点降尺度工具；替代上文第三方转载条目，第三方仓库不使用）。
- Marzbanrad, J., Ahmadi, G., Jha, R. (2004). Optimal preview active control of structures during earthquakes. *Engineering Structures*, pp.1463–1471. https://doi.org/10.1016/j.engstruct.2004.05.010 （A2 节点，预视控制理论参照）。
- Abdelaziz, K. M., Alipour, A., Hobeck, J. D. (2021). A smart façade system controller for optimized wind-induced vibration mitigation in tall buildings. *JWEIA* 212:104601. https://doi.org/10.1016/j.jweia.2021.104601；Abdelaziz, K. M., Hobeck, J. D. (2022). Adaptive flow-induced vibration control using distributed sensor/actuator networks with gated recurrent units and genetic algorithms. *Proc. SPIE* 12046. https://doi.org/10.1117/12.2630805 （A2 节点先例）。
- US Patent 5,592,791 A (1997). Active controller for the attenuation of mechanical vibrations. https://patents.google.com/patent/US5592791A/en （A2 节点，建筑上游测风前馈方案）。
- A2 最小试验数据：本线复用数字孪生风洞线 Silsoe v7 LBM-LES 时程（非公开数据产品，只引结论与路径）。
- Construction Plant-hire Association (2025). *Planning & Control of Lifting Operations in Wind*, CIG/TCIG 2507 V1, July 2025. https://cpa.uk.net/wp-content/uploads/2025/08/CPA-T_CIG-2507-Planning-Control-of-Lifting-Operations-in-Wind-V1-July-2025.pdf （F 节点吊装风速阈值来源）。
- Browell, J., Dinwoodie, I., McMillan, D. (2016). Forecasting for day-ahead offshore maintenance scheduling under uncertainty. ESREL 2016. https://strathprints.strath.ac.uk/56764/ （F 节点，成本/损失+logistic 概率决策先例）。
- Richardson, D. S. (2000). Skill and relative economic value of the ECMWF ensemble prediction system. *QJRMS* 126:649–667. https://doi.org/10.1002/qj.49712656313 （F 节点相对经济价值 V 定义）。
- HS2 Learning Legacy. A weather resilient approach to construction: lessons from Align joint venture on HS2. https://learninglegacy.hs2.org.uk/document/a-weather-resilient-approach-to-construction-lessons-from-align-joint-venture-on-hs2/ （F 节点，施工吊装 AI 订正预报先例）。
- Zhu, Y., Toth, Z., Wobus, R., Richardson, D., Mylne, K. (2002). The economic value of ensemble-based weather forecasts. *BAMS* 83:73–83. https://doi.org/10.1175/1520-0477(2002)083<0073:TEVOEB>2.3.CO;2 （F 节点 V 公式）。
- National Highways, The Severn Bridges; Mackinac Bridge Authority FAQ; OSHA 29 CFR 1926.1431 （F 节点桥梁/吊人风速阈值）。
- NOAA NWS, Damage Assessment Toolkit (DAT) public FeatureServer, https://services.dat.noaa.gov/arcgis/rest/services/nws_damageassessmenttoolkit/DamageViewer/FeatureServer （I 损失–风速库：灾后损伤点可获得性）。
- NOAA NWS, Directive 10-1605 Storm Data Preparation, https://www.weather.gov/directives/ （I：估计风速依据，附录 A §46.3、§24）。
- StEER Hurricane Ian dataset, DesignSafe PRJ-3709, DOI 10.17603/ds2-f1p1-ev62 （I：灾后调查报告可获得性）。
- Xu, W., Balaguru, K., Judi, D. R. et al. (2024). A North Atlantic synthetic tropical cyclone track, intensity, and rainfall dataset (RAFT). *Scientific Data* 11, 130. https://doi.org/10.1038/s41597-024-02952-7；数据 https://zenodo.org/records/10392725 （CC BY 4.0）
- Bloemendaal, N. et al. (2020). Generation of a global synthetic tropical cyclone hazard dataset using STORM. *Scientific Data*.

### B2 合成台风设计风速第一轮（10-14）
- Emanuel, K., Ravela, S., Vivant, E., & Risi, C. (2006). A Statistical Deterministic Approach to Hurricane Risk Assessment, supplement, *BAMS* 87, 299–314. https://texmex.mit.edu/pub/emanuel/PAPERS/hurr_risk_suppl.pdf （B2 RAFT 生成位置核的历史 HURDAT 概率定义，PDF 第 1 页；不含该 RAFT 子集的年发生率）。
- NOAA National Hurricane Center (2026). Atlantic HURDAT2 best track, 1851–2025, file issued 2026-09-23. https:/ （B2 RAFT 等效年率的 1979–2018 观测代理，10 m 1-min 最大持续风）。
- Bloemendaal, N., Haigh, I. D., de Moel, H., Muis, S., Haarsma, R. J., & Aerts, J. C. J. H. (2020). Generation of a global synthetic tropical cyclone hazard dataset using STORM. *Scientific Data* 7, 40. https://doi.org/10.1038/s41597-020-0381-2；去重并修正飓风等级的 v4 数据：https://doi.org/10.4121/12706085.v4 （B2 使用北大西洋 10,000 年目录）。
- Simiu, E., Vickery, P. J., & Kareem, A. (2007). Relation between Saffir-Simpson hurricane scale wind speeds and peak 3-s gust speeds over open terrain. *Journal of Structural Engineering*. https://doi.org/10.1061/(ASCE)0733-9445(2007)133:7(1043) （B2 热带气旋 1 min 开阔水面→3 s 开阔地貌换算候选；本地卡 2E23NHAE PDF 第 1–3 页，卡尚待独立）。
- American Society of Civil Engineers (2022). ASCE/SEI 7-22 风害地点数据 50/700 年 MRI，ArcGIS ImageServer `w2022_mri50w2022_mri700`，https://gis.asce.org/arcgis/rest/services/ASCE722/ （B2 逐点 identify；10 m Exposure C 3 s 阵风；非 PDF 读图）。
- Iowa State University / Iowa Environmental Mesonet (2026). ASOS 站点 GeoJSON 元数据，https://mesonet.agron.iastate.edu/geojson/network/FL_ASOS.geojson （B2 19 机场站坐标，不取观测风；KPBI 已改称 KDJT，按同址坐标留冻结旧名）。
- Gao, Y. & Xi, D. (2026). SPIN (v1.0): A spontaneous synthetic tropical cyclone model empowered by NeuralGCM for hazard assessment. *Geosci. Model Dev.* 19, 7303–7323. https://doi.org/10.5194/gmd-19-7303-2026；输出 https://doi.org/10.5281/zenodo.20795548 （B2 第三链可用性核验）。
- Bose, R., Pintar, A. L., & Simiu, E. (2023). Simulation of Atlantic Hurricane Tracks and Features: A Coupled Machine Learning Approach. *Artificial Intelligence for the Earth Systems* 2(2). https://doi.org/10.1175/AIES-D-22-0060.1 （B2 第三链目录可用性核验）。

### ftkb 第四轮书籍盲测（10-14；不公开题目或答案）
- Arya (2001), *Introduction to Micrometeorology*, https://search.worldcat.org/search?q=[已隐去]。
- Strikwerda (2004), *Finite Difference Schemes and Partial Differential Equations*, https://search.worldcat.org/search?q=Finite+Difference+Schemes+and+Partial+Differential+Equations+Strikwerda。
- Tory & Frank (2010), “Tropical Cyclone Structure and Dynamics,” https://search.worldcat.org/search?q=Tropical+Cyclone+Structure+and+Dynamics+Tory+Frank。
- Anthes (1982), *Tropical Cyclones: Their Evolution, Structure and Effects*, https://search.worldcat.org/search?q=Tropical+Cyclones+Their+Evolution+Structure+and+Effects+Anthes。
- American Society of Civil Engineers (2021), *Wind Tunnel Testing for Buildings and Other Structures*, ASCE 49-21, https://search.worldcat.org/search?q=ASCE+49-21+Wind+Tunnel+Testing。
- Halverson (2024), *An Introduction to Severe Storms and Hazardous Weather*, https://search.worldcat.org/search?q=Introduction+to+Severe+Storms+and+Hazardous+Weather+Halverson。
- Anderson (本地扫描 PDF 未给年份), *Computational Fluid Dynamics: The Basics with Applications*, https://search.worldcat.org/search?q=Computational+Fluid+Dynamics+The+Basics+with+Applications+Anderson。
- Mathews & Walker (1970), *Mathematical Methods of Physics*, https://search.worldcat.org/search?q=Mathews+Walker+Mathematical+Methods+of+Physics。
- Wilcox (本地 PDF 文件名 2010), *Turbulence Modeling for CFD*, https://search.worldcat.org/search?q=Wilcox+Turbulence+Modeling+for+CFD。
- Dahlquist & Björck (1974), *Numerical Methods*, https://search.worldcat.org/search?q=Dahlquist+Bjorck+Numerical+Methods。
- Naudascher & Rockwell (1994), *Flow-Induced Vibrations*；Haltiner & Martin (1957), *Dynamical and Physical Meteorology*：本轮复用，链接见本页文献节既有条目。
- Iowa Environmental Mesonet (IEM), ASOS/AWOS METAR download, https://mesonet.agron.iastate.edu/request/download.phtml （I 损失–风速库：DAT 损伤点邻站实测阵风）。
- Prevatt, D. O., Kameshwar, S., Roueche, D. B., et al. (2021), StEER: Hurricane Ida Joint PVRR-EARR, DesignSafe / ThinkTech, https://doi.org/10.17603/ds2-w6km-fe51 （I r3 公开调查报告；本轮未取逐点表）。
- StEER Network (2023), Hurricane Idalia 项目 PRJ-4123, DesignSafe-CI, https://www.designsafe-ci.org/data/browser/public/designsafe.storage.published/PRJ-4123 （I r3 公开项目目录；本轮未取逐点表）。
- NOAA NWS, Downbursts, Nashville Weather Forecast Office, https://www.weather.gov/ohx/downbursts （I r3 雷暴微/宏下击暴流一般尺度说明，网页无页码，非 DAT 逐点机理判别）。
- Romanic, D., Taszarek, M., Brooks, H. (2022). Convective environments leading to microburst, macroburst and downburst events across the United States. Weather and Climate Extremes 37:100474. https://doi.org/10.1016/j.wace.2022.100474 （I：下击暴流足迹尺度）。
- NOAA JetStream, Thunderstorm Hazards – Damaging Wind, https://www.noaa.gov/jetstream/thunderstorms/thunderstorm-hazards （I：微/宏下击暴流尺度）。
- Manzini, T., Perali, P., Karnik, R., & Murphy, R. (2024), *CRASAR-U-DROIDs: A Large Scale Benchmark Dataset for Building Alignment and Damage Assessment in Georectified sUAS Imagery*, https://arxiv.org/abs/2407.17673；数据 CRASAR (2024–2026), https://huggingface.co/datasets/CRASAR/CRASAR-U-DROIDs （CC BY 4.0；I r4 Ida/Idalia/Ian 建筑无损分母候选，注意多视图去重及影像覆盖选样）。
- Defense Innovation Unit / xView2, *xBD Dataset*, https://xview2.org/dataset （CC BY-NC-SA 4.0；I r4 仅数据可得性备选，未批量下载）。
- USACE, *National Structure Inventory 2022*, https://www.arcgis.com （I r4 建筑存量候选，不提供事件无损标签）。
- FEMA, *OpenFEMA Housing Assistance Program Data – Owners v2*, https://www.fema.gov/openfema-data-page/housing-assistance-program-data-owners-v2 （I r4 邮编汇总无损检查数，非逐栋坐标）。
- NOAA National Weather Service / Unidata (2024–2025), NEXRAD Level II KFWS public archive mirror, https://unidata-nexrad-level2.s3.amazonaws.com/ （H6 两个 Dallas 事件最低仰角速度；雷达体扫在内存解码，不保留原始文件）。
- NOAA National Weather Service / Unidata (2024), KLOT NEXRAD Level II archive mirror, https://unidata-nexrad-level2.s3.amazonaws.com/ （H7 Chicago 候选事件最低仰角速度；仅内存解码，不留原始体扫）。
- Helmus, J. J. & Collis, S. M. (2016), The Python ARM Radar Toolkit (Py-ART), *Journal of Open Research Software* 4:e25, https://doi.org/10.5334/jors.119 （H6 去混叠与门解码）。
- USGS (2026), 3DEP Bare Earth DEM Dynamic Image Service, https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer （I r5 建筑质心地面高程；现版用于 2021–23 回溯有时序错配）。
- USGS (2026), Elevation Point Query Service (EPQS), https://epqs.nationalmap.gov/v1/json （H7 DAT 点地面高程复核；现代 3DEP 地形用于 2024 回溯有时序错配）。
- NOAA National Hurricane Center (2022, 2023), Potential Storm Surge Flooding archived GIS GeoTIFF, Ian https://www.nhc.noaa.gov/gis/archive_inundation_results.php?id=al09&year=22&name=Hurricane%20IAN; Idalia https://www.nhc.noaa.gov/gis/archive_inundation_results.php?id=al10&year=23&name=Hurricane%20IDALIA; guide https://www.nhc.noaa.gov/gis/inundation/potential_storm_surge_flooding_downloads_guide.pdf （I r5 仅作潜在水损风险筛查，非实际淹没）。
- NOAA National Hurricane Center (2026), Tropical Cyclone Report: Hurricane Ian (AL092022), https://www.nhc.noaa.gov/data/tcr/AL092022_Ian.pdf （I r5 潮水/雨洪机制背景；本轮只用于筛查限制，不作逐栋归因）。
- NOAA NHC, Potential Storm Surge Flooding maps (Ian advisory 27, Idalia advisory 16), https://www.nhc.noaa.gov/surge/inundation/；USGS 3DEP bare-earth DEM （I：r5 水损风险筛查）。
- Cangialosi, J. P., Alaka, L. (2024). National Hurricane Center Tropical Cyclone Report: Hurricane Idalia (AL102023). https://www.nhc.noaa.gov/data/tcr/AL102023_Idalia.pdf （I：核对重建风速是否超过登陆强度）。
- Asmuth et al. (2021). Wall-modeled lattice Boltzmann large-eddy simulation of neutral atmospheric boundary layers. Physics of Fluids. https://doi.org/10.1063/5.0065701 （LUW 地面壁面模型原型的方法依据）
- Haussmann et al. (2019). Large-eddy simulation coupled with wall models for turbulent channel flows at high Reynolds numbers with a lattice Boltzmann method. Computers & Mathematics with Applications 78, 3285–3302. https://doi.org/10.1016/j.camwa.2019.04.033 （同上）
- Han et al. (2021). A wall function approach in lattice Boltzmann method: algorithm and validation using turbulent channel flow. Fluid Dynamics Research. https://doi.org/10.1088/1873-7005/ac1782 （同上，备选方案）
- Spinelli et al. (2024). Key ingredients for wall-modeled LES with the lattice Boltzmann method. DCDS-S 17(11), 3224–3251. https://doi.org/10.3934/dcdss.2023212 （同上，近壁 SGS 诊断）
- Malaspinas, O., Sagaut, P. (2014). Wall model for large-eddy simulation based on the lattice Boltzmann method. Journal of Computational Physics. https://doi.org/10.1016/j.jcp.2014.06.020 （LUW 壁面模型第二层匹配高度对照）
- Shin, E. Y., Yang, X. I. A., Howland, M. F. (2025). Addressing grid convergence and log-layer mismatch in wall modeled LES of geophysical flows over rough surfaces and canopies. Boundary-Layer Meteorology 191, 42. https://doi.org/10.1007/s10546-025-00934-9 （同上）
- Mason, P. J., Thomson, D. J. (1992). Stochastic backscatter in large-eddy simulations of boundary layers. Journal of Fluid Mechanics 242. https://doi.org/10.1017/S0022112092002271 （LUW 壁面模型近壁亚格子阻尼变体）
- Zhang, J.; Shao, J. 小语言模型重构高等教育课程、教材、教法 / Small Language Models Reshape Higher Education: Courses, Textbooks, and Teaching（预印本，Liang Hu 10-15 提供；资料链接见文末百度网盘）。
- Zhang, J. (2025). Small Language Models Offer Significant Potential for Science Community. arXiv:2510.18890.
- Zhang, J. (2026-01-27). 小语言模型重塑科学与高等教育（100 页报告 PPT，Liang Hu 10-15 提供）。
- **PyMuPDF / MuPDF**（Artifex Software，AGPL-3.0；1.28.x）：https://github.com/pymupdf/PyMuPDF （文献图库节点：从 PDF 抽取图像区域、图注文本块与页面渲染；此前台式机文本重抽亦用它）。
- **Pillow**（Python Imaging Library 分支，MIT-CMU）：https://python-pillow.github.io/ （文献图库节点：缩略图与抽样拼图）。
- **FastEmbed**（Qdrant，Apache-2.0）与 **ONNX Runtime**（Microsoft，MIT）：https://github.com/qdrant/fastembed，https://onnxruntime.ai/ （文献图库节点：图注多语言向量重排，CPU 推理）。
- **Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q**（Apache-2.0，量化自 sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2）：https://huggingface.co/Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q


## 快试实验室

本页展示的快试使用了以下公开数据、代码、工具与文献。转引本页内容时请引用原始来源。（由快试实验室 Lead 维护：新用到外部数据、代码、模型、工具或文献时，在这里补一条。）

- svg-diagram：bybit-exchange，GitHub 仓库 https://github.com/bybit-exchange/svg-diagram，MIT 许可，所用提交 c30c9e3（快试 #15，10-16）。
- 科研绘图 Skill 候选（快试 #12，10-16）：AgentFigureGallery、Nature Skill、Academic Figure Skill、Origin Style Replot、figures4papers、K-Dense Scientific Visualization。实际试用：Academic Figure Skill，TingxiYu，https://github.com/TingxiYu/academic-figure-skill，Apache-2.0（以 LICENSE 文件为准），提交 1df9940dd0；K-Dense Scientific Visualization，K-Dense-AI，https://github.com/K-Dense-AI/scientific-agent-skills （skills/scientific-visualization），MIT，提交 a1043ef544。
