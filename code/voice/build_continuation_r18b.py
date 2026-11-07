#!/usr/bin/env python3
"""Nine further source-anchored draft cards; do not overwrite cards."""
import csv,pathlib,subprocess,re,hashlib
ROOT=pathlib.Path(__file__).resolve().parent
R={x['archive_id']:x for x in csv.DictReader((ROOT.parent/'archive_index/kareem_archive_index.csv').open(encoding='utf-8-sig'))}
# All quotations copied from specific physical pages; do not interpolate OCR glyphs.
D={
'KA-0060':('2002 年 Kareem/Kijewski 探索时间频率联合分析以处理风致响应的时变特征。',[
(1,'对带非线性/非平稳特征的过程，仅用傅里叶变换可能无法完整刻画。','As many physical processes of interest to Civil Engineers manifest nonlinear and nonstationary features, their complete characterization may not be accomplished via Fourier transforms, necessitating a new analysis framework in the time-frequency domain.'),
(17,'小波的工程应用须处理信号处理层面的风险，不把任何时频图当作自动可靠答案。','Despite the merits of these analyses, it should be noted that a number of processing concerns must be addressed in order to obtain reasonable results, particularly for the class of signals of relevance to Civil Engineering [9–11].')],
'与 Kijewski 合著；小波应用尚在初期；未论证可以替代所有频域分析。','对照 KA-0559 第 32 页全尺度拍频案例：2002 提出分析框架，2005 报告给出特定耦合楼实例，并非普适证明。','没有给短记录下稳健估谱的统一窗口与误差阈值。','检视第 1–17 页章节、方法实例与结论；图示和时频数值未逐像素核读。'),
'KA-0102':('1997 年单作者文比较矩形体表面随机压力场在不同入流湍流及条件采样下的时空相关。',[
(3,'即使湍流强度升高减弱涡脱落，压力仍可在 Strouhal 频率保有显著能量；文中也列出与他人不同的观察。','While increased turbulence intensity vitiates the vortex shedding process, nonetheless pres- sure fluctuations still exhibit significant energy at the Strouhal frequency.'),
(9,'分离泡中有显著展向相关峰，但下游侧面相关减弱；不能把上游峰简单推广到整面。','The spanwise correlation of both conditional and unconditional pressure data in the separation bubble is very pronounced, suggesting existence of spatially and temporally well- correlated peaks in pressure.')],
'只涉及实验矩形/方形棱柱与本文边界层；第 3 页把与 Saathoff/Melbourne 不同的现象归因于流场及二维/三维条件，不能定为他人结果错误。','与 KA-0221 对湍流与侧面压力相关的观察相近，试验体系是否独立尚待核。','没有通用面板峰压空间相关长度；条件采样触发阈值不可移用。','检查 PDF 第 1–9 页引言、实验、条件采样、结论；图/表数值未人工逐项复测。'),
'KA-0104':('1983 年单作者文讨论高楼使用性与调谐质量阻尼器的设计条件。',[
(1,'高楼运动控制不仅是构件强度，也关系于住户体验。','Serviceability of a building is affected by excessive acceleration experienced at the top floors in wind storms that may cause discomfort to the building occupants.'),
(1,'个体对摇晃的感受存在差异，不能把舒适度表述成单一确定性生理阈值。','Overall biodynamical response of the human body varies in a random fashion from person to person.'),
(10,'等效单自由度吸振器分析依赖主结构固有频率充分分离的条件。','It is also shown that a building with well separated natural frequencies can be adequately represented by an equivalent single-degree-of-freedom main system for the analysis of a dynamic vibration absorber.')],
'频率分离是假设，TMD 案例不能直接转为所有高楼的阻尼器配置；文内人群舒适研究亦多引自前人。','与 KA-0142 的液体调谐阻尼器不是同一阻尼器类型；不能合并为一个控制律。','没有适用所有高楼住户的统一加速度阈值。','阅读 PDF 第 1–9 页理论与案例、结论；第 10–12 页为结尾及参考文献，图表未逐像素核。'),
'KA-0135':('1992 年单作者综述性方法文把高楼风洞试验、横扭耦合和使用性判断接到初步设计决策。',[
(2,'力天平给特定几何和环境下的荷载，而在横扭模态及非线性形状时有修正限制。','The force balance technique has some shortcomings, e.g., only approximate estimates of the mode-generalized torsional moments are obtained and the lateral loads may be inaccurate if the sway mode shapes of the structure differ significantly from a linear mode shape.'),
(6,'当质量中心与刚度中心偏心时，平动/扭转解耦不再可直接使用。','For a building with eccentric mass and resis- tance centers, generally referred to as torsionally coupled, the preceding simplifica- tion is not possible and the analysis becomes computationally more involved.')],
'本文所举风洞为特定矩形及组合模型，早期 HFFB 修正的限制与今天所有试验设备不能划等号。','与 KA-0559 第 2–3 页的耦合/相关分析相接，2005 文增加了多向相关条件。','没有一条无需风洞即可适用任意自由形体高楼的荷载系数。','核读 PDF 第 1–11 页设计流程、模型、风洞与结论，第 12 页参考文献；图表未复数值。'),
'KA-0141':('1987 年单作者文检视一或两座上游棱柱对下游棱柱振动的有利及不利干扰。',[
(5,'城市建筑间干扰可能改善也可能加剧风致振动，不能一概视为遮挡减载。','The results of various configurations presented may provide guidance to the designers of prismatic tall buildings concerning the likelihood of adverse, or beneficial mutual interference and proximity effects'),
(8,'局部脉动压力并未在本文研究，外推至不同几何与边界层需谨慎。','Furthermore, the magnitude of the localized fluctuating pressure on buildings, which was not investigated here, may be influenced differently under different boundary con- ditions due to interference and proximity effects.')],
'本文第 7–8 页明确限定等高/等平面尺寸棱柱和选定排列，第一摘句是原文排版无句号的句段，需人工对原版确认句界。','与 KA-0221 的孤立棱柱压力场不同，不能将邻楼干扰倍数转成单栋立面峰压。','没有任意建筑群布局的全尺度验证或局部面板极值规律。','审阅 PDF 第 1–8 页设计、速度谱与结论；图 3–6 曲线未数字化。'),
'KA-0178':('1989 年单作者方法文比较点压力、面积/时间平均压力与整体/模态广义荷载的测量接口。',[
(1,'要估算局部和整体荷载，需要压力场的时空分布而不是一个点压峰值。','Information on the spatial and temporal distributions of random pressure fields around structures is central to the development of analytical procedures for estimating local and/or integral aerodynamic load effects on structures.'),
(7,'可用加权气动平均法测横向与扭转模态广义荷载，但属于实用测量手段而非无需验证的精确通则。','The weighted pneu- matic averaging facilitates convenient measurement of the lateral and tor- sional mode-generalized loads on tall and long-span structures.')],
'文中对聚簇测点与高频信号存在空间平均误差提示；不能把“holds promise”说成已证所有结构与频段。','与 KA-0119 顺风压力场合成有方法接口，二者不能证明一个点压取代广义荷载。','未提供面板、桥面、楼层结构共同适用的点压到总力转换常数。','阅读 PDF 第 1–7 页测量原理、图示说明、示例与结论，第 8 页主要参考文献；图/传感器示意未视觉逐项核。'),
'KA-0192':('1990 年单作者文比较风敏感结构可靠度计算的近似、数值积分和仿真路线。',[
(13,'对非线性极限状态/非正态基本变量，MFOSM 指标须谨慎使用。','The results from this approach should be interpreted cautiously unless the limit state func- tion happens to be linear and the basic variables are normally distributed.'),
(17,'数值积分受维数限制，MFOSM 近似的适用域包括线性状态和正态基本变量。','However, the applicabilityofthe MFOSM isrestricted to problem domains with linear limit state functions and normal basic vari- ables.')],
'第 9–17 页为钢筋混凝土烟囱示例，频率/阻尼等分布是该算例假设；第二句 OCR 连字，引用时应与 PDF 版式对照。','与 KA-0215（1988）从参数传播到结构可靠度的关切相承，但不把示例随机变量分布当统一标准。','极低失效概率尾部需要更多可靠观测；该文不提供今日任意建筑的真实可靠度。','检视 PDF 第 1–17 页方法及算例、结论，后续页主要参考文献；表 1–3 数字和公式未视觉逐项核。'),
'KA-0221':('1990 年单作者文用压力测点和积分荷载比较棱柱表面的随机压力结构。',[
(9,'分离泡侧面展向相关峰显著，而靠近下游边界时减弱。','The spanwise correlations on the side faces are very pronounced in the separation bubble, whereas near the downstream edge less evidence of correlation is exhibited.'),
(9,'其积分荷载与力天平结果吻合是本研究棱柱和实验条件下的交叉验证。','The integral aerodynamic loads derived from the averaging of the random pressure field over the prisms provided good agreement with the values obtained from the high-frequency force balance measurements.')],
'限定于棱柱湍流边界层模型；第 9 页条件采样长度依赖触发水平，不作为一般常数。','与 KA-0102 对压力相关结构同向，但不是独立复制验证（实验来源/数据关系待核）。','没有复杂城市建筑物或阵风锋的通用压力峰值转换。','检视第 1–9 页实验与结论，后续参考文献；图曲线未逐点视觉复核。'),
'KA-0320':('2017 年 Kareem/Kwon 合作论文提出 VORTEX-Winds 作为共享风荷载工具和数据的网络组织。',[
(1,'复杂基础设施设计与风灾数据分散促成合作式设施的需求，但“新范式”是本文倡议而非效果已证。','With the trend toward increasingly complex designs of civil infrastructure combined with the escalating potential for losses by extreme wind events, a new culture of research needs to be established based on innovative and collaborative solutions for better man- agement of the impact of extreme wind events.'),
(30,'截至论文发表时，一些模块仍为测试版或有访问限制，不得当成全部已开放/成熟。','Some of the modules are still being beta tested and others are restricted and require additional registration and login for additional firewall equipment of cloud platform and external servers.')],
'2017 文为合作成果；不使用贡献声明校正写作来源；当时模块状态不能表述为当前在线可用。','与 KA-0561（2009，第 21–27 页）虚拟组织愿景相连，2017 文报告具体平台状态，无法据此推出现今网站状态。','未提供各模块跨机构可复现的性能基准或当前服务可用性。','检视 PDF 第 1–30 页章节和工具列表及总结；图表界面和第 31 页后附录未全部核验。')
}
def norm(s):
 s=re.sub(r'(?<=\w)-\s+(?=\w)','',s)
 return re.sub(r'\s+',' ',s).strip()
for k,(problem,claims,limits,relation,gaps,scope) in D.items():
 row=R[k];path=pathlib.Path(row['local_pdf_path'].split(';')[0]);assert path.is_file(),path
 pages=subprocess.run(['pdftotext','-raw',str(path),'-'],capture_output=True,text=True,check=True).stdout.split('\f')
 blocks=[]
 for n,zh,q in claims:
  assert 1<=n<=len(pages) and norm(q) in norm(pages[n-1]),(k,n,q)
  blocks.append(f'- {zh}（PDF 物理第 {n} 页）\n  > {q}')
 s=f'''# {k} 立场卡（续读工作稿）

① 文献与层：{row['title']}（{row['year']}），{k} / {row['work_id'] or '无旧 work_id'}；元数据层 {row['tier']}，作者序 {row['kareem_position']}。年份和作者序并非实际写作者证据。
PDF：`{path}`；SHA-256：`{hashlib.sha256(path.read_bytes()).hexdigest()}`。

② 问题：{problem}

③ 原文支撑的论证节点（须保留研究对象/前提）：

{chr(10).join(blocks)}

④ 限制/警告：{limits}

⑤ 与较早/晚材料的关系：{relation}

⑥ 未回答：{gaps}

阅读记录：{scope} 此卡为定向阅读的工作稿，不冒称全篇逐段及图表核毕。
'''
 out=ROOT/'cards'/f'{k}.md'
 if out.exists():
  assert out.read_text(encoding='utf-8')==s,f'existing result differs {out}'
 else:
  out.write_text(s,encoding='utf-8')
print('new_cards',len(D),'checked_quotes',sum(len(x[1]) for x in D.values()))
