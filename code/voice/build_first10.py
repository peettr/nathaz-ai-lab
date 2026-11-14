#!/usr/bin/env python3
"""Source-anchored first batch. Only writes voice/cards and voice_overview.md."""
import csv, pathlib, subprocess, re, hashlib
ROOT=pathlib.Path(__file__).resolve().parent
INDEX=ROOT.parent/'archive_index/kareem_archive_index.csv'
rows={r['archive_id']:r for r in csv.DictReader(INDEX.open(encoding='utf-8-sig'))}
# (PDF physical page, claim, short source excerpt)
items={
'KA-0500':[(24,'以使用期间的运动舒适度限制作为高层建筑设计问题。','This has made it necessary to design tall buildings that will not exceed specified motion levels in prescribed time intervals.'),(327,'不要把阻尼估计当成和几何尺寸同样确定的输入。','For this reason damping generally is much more difficult to predict.'),(334,'准定常假设的适用性随湍流强度和约化风速变化，不能在常规运行范围直接照搬。','However, with an increase of turbulence intensity and reduced velocities corresponding to the normal operational range of typical tall buildings, the validity of quasi-steady assumptions is progressively jeopardized.')],
'KA-0156':[(1,'以概率框架评估风与结构参数不确定性下的性能和可靠度。','The element of uncertainty inherent in the parameter space, e.g., wind speed and structural characteristics, introduces variability in the estimates of wind effects that requires a probabilistic framework to assess structural performance and associated measures of structural reliability.'),(5,'围护构件局部压力峰值不能直接在受荷面积上相加，否则会高估荷载。','An averaged value of the peak pressures, based on the point peaks observed at several locations on the tributary area, will overestimate the peak structural load because the lack of spatial and/or temporal correlation does not permit simultaneous occurrence of the maxima at several locations.'),(22,'将阻尼量化作为结构动力分析中的重要不确定性来源。','Quantification of damping is by far the most vexing problem in structural dynamics.')],
'KA-0085':[(7,'风场模拟需要检查无散条件以及进入计算域后的湍流衰减。','One of the issues for these simulations is to ensure that the ﬂow is divergence free, which may require an iterative approach and should also consider the decay of turbulence as the ﬂow moves into the computational domain.'),(16,'截断高阶模态用于局部荷载/响应时可能低估其效应。','However, truncation of higher modes may not work effectively in the case of local response, which may lead to an underestimation of the local wind loads and their effects (Chen and Kareem, 2005).'),(20,'桥梁线性气动力模型有实用价值，但不足以全面处理非线性和湍流效应。','Therefore, one may conclude that current linear force models have proven their utility for a number of practical applications; however, these fail to completely address the challenges posed by aerodynamic nonlinearities and turbulence effects.')],
'KA-0372':[(1,'对阵风锋等问题，超越只适合平稳线性描述的常规框架，处理非平稳、非高斯和非线性。','Yet there remain several frontiers that still need to be addressed for example the three “Nons,” the triple emerging fronts, i.e., non-stationarity, non-Gaussianity, non-linearity'),(2,'CFD 面对结构周围大尺度分离、入流多尺度波动及非线性相互作用的数值刻画难题。','The major challenge in CFD is the difﬁculty in numerically capturing the complexity of massively separated ﬂows around structures compounded by multi-scale ﬂuctuations in the inﬂow turbulence and their nonlinear interactions.'),(3,'设计不确定性必须考虑入流与模型形式的耦合及有限计算资源。','Design-under-uncertainty encounters challenges stemming from uncertainty quantiﬁcation of the coupled inﬂow and model-form uncertainties with limited availability of computational resources.')],
'KA-0078':[(3,'单一响应指标的阵风荷载因子不能用于均值为零的响应。','However, the response- speciﬁc GLF also has shortcomings since each response component requires a separate GLF and in the case of zero mean response, this approach fails like the conventional one.'),(8,'区分等效静力/诱导荷载与外施空气动力荷载。','It is important to distinguish clearly between the equivalent-static/induced and the aerodynamic/externally applied wind loads.'),(16,'高层建筑设计不能只看顺风响应：横风和扭转对正常使用及安全也重要。','In many cases, the wind-induced response due to acrosswind and torsional excitations is as important as the alongwind in terms of both serviceability and survivability design of tall buildings.')],
'KA-0030':[(2,'长柔桥梁的风致响应既关乎稳定性，也关乎入流湍流激励的抖振。','The response of a long flexible bridge to wind is sensitive not only to stability; buffeting due to incident turbulence also becomes important.'),(3,'尖角钝体在湍流边界层中的气动认识尚不完备。','our knowledge of the aerodynamics of sharp-edged bluff bodies in turbulent boundary layer flows is far from complete.'),(4,'灾后调查对木结构风损重要，但分析研究可探查难以在全尺度观测中改变的条件。','Post-disaster investigations have been the principal source of information on wind damage to wood-frame houses; however, analytical studies can be used to predict the effect of wind on wood-frame houses under a variety of conditions which are otherwise difficult to vary and simulate in full-scale tests or post- disaster observations.')],
'KA-0291':[(2,'横风等风荷载不可直接当成顺风问题用解析阵风因子处理。','The problems of wind loads on structures, with the exception of alongwind loads (in the direction of wind) , cannot be treated satisfactorily by analytical methods, e.g., gust factor approach (5).'),(3,'测模型脉动力时，力天平系统固有频率必须高于所测激励频率且传感器足够灵敏。','the resonant fre- quency of the entire system must be higher than any expected forcing frequency and at the same time the transducer should have a high sensitivity.'),(5,'侧面分离和再附着导致非均匀压力场，整面相关函数难以简单解析描述。','inhomogeneity in the pressure field arising out of complexities of turbulent shear flow interaction with a bluff body, separation and reattachment phenomenon prohibits any simple analytical description of crosscorrelation or eo-spectrum for the entire face.')],
'KA-0217':[(4,'风致响应参数不确定性不仅源于材料，也源于制作和数学理想化。','Uncertainty in the system parameters such as mass, stiffness and damping may arise either from spatially random variations in the material, its fabrication, or its mathematical idealization.'),(5,'描述多点随机风场要保留空间相干性。','Regarding the multi-point representa- tion of random wind field the description of spatial coherence is essential for any functional description.'),(13,'响应不确定性估计可作为极限状态与可靠度设计的输入，而不是单一确定性值。','These estimates of uncertainty in the response may provide a useful input to establish a limit-state design procedure, or reliability analysis of structures to ensure their safety and serviceability.')],
'KA-0142':[(1,'高层建筑运动控制除安全外，还须考虑舒适度和正常使用。','Besides various failure possibilities, cladding and partition damage, serviceability of a building is an important design criteria.'),(2,'调谐液体阻尼器模型应允许阻尼随振幅和方向变化。','To correctly model the contribution of a TSD to the dynamical behavior of the combined system, the transfer function of the TSD must account for the resultant changes in damping values for differentmotion amplitudes and directions.'),(5,'即使子系统各自采用比例阻尼，耦合系统通常也不是模态阻尼。','It is also important to note that in general, the combined systems are not modally damped even if it is assumed that each of the two subsystems are proportionally damped.')],
'KA-0031':[(2,'横风和扭转主要由不易用入流湍流表征的非定常尾流激励，不能直接用阵风因子处理。','The acrosswind response and torsional re- sponse cannot be treated in terms of gust factors inasmuch as they are induced by the unsteady wake fluctuations which cannot be conve- niently expressed in terms of the incident turbulence.'),(4,'极细长、柔且低阻尼结构在高约化风速下要考虑运动相关的气动阻尼。','However, for exceptionally slender, flexible, and lightly-damped structures at high reduced velocities, the aerodynamic damping associ- ated with velocity dependent forces can become significant.'),(16,'高层建筑的漂移和加速度使用性限值应覆盖横移与扭转耦合。','The significance of the torsional as well as the acrosswind response suggests that the criteria limiting the maximum drift and acceleration of high-rise build- ings, as a serviceability limit state, must address the lateral-torsional mo- tion.')],
}

def norm(s):
 s=re.sub(r'(?<=\w)-\s+(?=\w)', '', s)
 s=re.sub(r'\s+([,.;:!?])',r'\1',s)
 return re.sub(r'\s+',' ',s).strip()
def page_texts(path):
 raw=subprocess.run(['pdftotext','-raw',str(path),'-'],capture_output=True,text=True,check=True).stdout
 return raw.split('\f')[:-1]

cards=ROOT/'cards'; cards.mkdir(exist_ok=True)
validated=[]
for key, claims in items.items():
 r=rows[key]; path=pathlib.Path(r['local_pdf_path'].split(';')[0]); assert path.is_file(),path
 pp=page_texts(path); blocks=[]
 for n,(pg,zh,q) in enumerate(claims,1):
  assert 1<=pg<=len(pp),(key,pg,len(pp))
  assert norm(q) in norm(pp[pg-1]),(key,pg,q)
  blocks.append(f'{n}. {zh}（PDF 物理第 {pg} 页）\n   > {q}')
  validated.append((key,pg,q))
 # We label inspection scope honestly: entire file electronically traversed, targeted sections read.
 meta=f'{r["title"]}（{r["year"]}）；{r["archive_id"]} / {r["work_id"] or "未配 work_id"}；{r["tier"]}；{r["kareem_position"]}；PDF {len(pp)} 页。'
 md=(f'# {key} 立场卡（首批定向阅读，非全文逐段审定）\n\n'
     f'① 文献与层：{meta}\n本地权威 PDF：`{path}`；SHA-256：`{hashlib.sha256(path.read_bytes()).hexdigest()}`。\n\n'
     f'② 面对的问题：{claims[0][1]} 此句仅作为本文主题定位，不等于证明其全部研究问题。\n\n'
     '③ 有原页锚点的主张/做法（以下摘句各不超过一句，连字符和排版保留 PDF 文字层原貌）：\n\n'+'\n\n'.join(blocks)+'\n\n'
     '④ 原文明确的局限/警告：见上列带限定的句子；本批未完成逐段阅读，其他局限待核，不作无证补写。\n\n'
     '⑤ 与其他时期说法的关系：本批不据题名或年代推断演变；需结合各篇上下文复核。\n\n'
     '⑥ 未回答的东西：当前摘录并不能证明本文对所有风型、结构类型和规范版本均适用；尚待全篇逐段核读。\n\n'
     '阅读记录：本机对全 PDF 文字层逐页扫描以定位引言、方法、讨论和结论；人工仅核上列页及附近段落。图表和其余段落未逐页语义精读，故此卡为阶段性交付，不能标为全文读毕。\n')
 out=cards/(key+'.md')
 if out.exists():
  assert out.read_text(encoding='utf-8')==md, f'existing result differs: {out}'
 else:
  out.write_text(md,encoding='utf-8')
print('cards',len(items),'validated excerpts',len(validated))
for key in items:print(key,len(page_texts(rows[key]['local_pdf_path'].split(';')[0])))
