#!/usr/bin/env python3
"""Versioned, non-overwriting source-page cards; never changes prior results."""
import csv, pathlib, subprocess, re, hashlib
ROOT=pathlib.Path(__file__).resolve().parent
INDEX=ROOT.parent/'archive_index/kareem_archive_index.csv'
ROWS={r['archive_id']:r for r in csv.DictReader(INDEX.open(encoding='utf-8-sig'))}
# page, interpretation, exact one-sentence excerpt from that PDF's text layer
DATA={
'KA-0561': {
 'problem':'2009 年主旨报告质询在瞬变/对流风、分离流、复杂城市环境中把稳态/准定常理论和简化规范直接外推的适用性；另论及协作式数据设施。',
 'claims':[
 (2,'准定常与带状理论在顺风抖振等大尺度低频湍流主导荷载时可用，分离流面压则不能由此简单建立入流—面压联系。','The quasi-steady theory fails to relate the approach flow and the ensuing pressure fluctuations on surfaces in separated flow regions.'),
 (4,'瞬变风可能产生超出传统定常统计描述的瞬时载荷，需重新审视荷载描述；所举研究是他引述的证据，不当作本人实验。','This clearly points at the need to critically assess the impact of abrupt changes in the wind field magnitudes and associated modifications in aerodynamics of structures and appraises the need for refining the current load descriptions.'),
 (11,'当阵风锋改变平均风速与方向时，传统风荷载估计的定常假设须重新检查。','This leaves the assumption of stationarity open to serious criticism.'),
 (17,'依赖表格、插值和外推的规范简化可能传递额外不确定性；作者倡议可追溯的数据库设计辅助。','The level of accuracy inherent in codification information in this format and the uncertainty associated with interpolation or extrapolation of information may compromise the overall accuracy in code-specified load effects.')],
 'limits':'2009 年综述大量转述 Sarpakaya、Kitagawa、Letchford 等实验，不可将其试验结果当作 Kareem 亲自测量；第 28 页致谢称 Kyle Butler 协助成稿，因此“单作者”只是署名，不证明独自写作。有关瞬变系数大小及特定规范修订该文未给可通用阈值。',
 'relation':'与 KA-0372（2020，第 1–3 页）同样列举非平稳及非高斯前沿；2009 的具体准定常适用性不能据此推定 2020 全盘否定准定常。与 KA-0085（2008，第 7 页）的 CFD 入流关切并列，主题相接而非相反。',
 'gaps':'不能从此综述推出所有阵风锋的设计系数、所有桥梁/建筑的峰值，亦不能替代被引原始下击暴流实验。',
 'scope':'阅读 PDF 第 1–28 页的章节结构及引言、准定常、瞬变、极端风、分析工具与协作框架；第 29–33 页为参考文献，未逐条核引用。图像和全部正文未逐图逐段人工核读。'},
'KA-0559':{
 'problem':'2005 年 Kareem 与 Chen 的 invited paper 对高层建筑横移—扭转耦合和长跨桥颤振/抖振的分析如何保留风荷载及模态相关性提出框架。',
 'claims':[
 (2,'结构主轴、力天平主轴不同及荷载分量相关时，不能套用互不相关的单向响应叠加。','In these cases proper care must be exercised to take into account the orientation of building principal axes, the force balance axes and any correlations that may exist among load components.'),
 (3,'在多向风荷载部分相关条件下，照搬单一地震输入的 CQC 模态相关系数可能有误。','The modal correlation coefficient of two adjacent modes depends not only on the frequencies and damping ratios, but also on the correlation/coherence of the generalized forces (Chen and Kareem 2005).'),
 (32,'全尺度案例中，模态拍频随时间出现，传统傅里叶谱未显示其演化；小波揭示了发生时段。','The analysis of coupled response of a full-scale building demonstrated that the evolution of a coalescent beat phenomenon responsible for high response level of the building was not apparent from conventional Fourier spectral perspective.')],
 'limits':'合作综述的桥梁方法多归因 Chen 及其合作者；摘要第 1 页及正文第 25–32 页将例子限定在耦合桥模态和所选全尺度建筑，不能推广“所有傅里叶方法无效”。PDF 第 4–30 页大量公式 OCR 字形破损，此卡不重写公式。',
 'relation':'与 KA-0078（2003，第 16 页）高楼横风/扭转不能被顺风响应掩盖同向，但此文增加荷载和模态交叉相关的具体前提；2003 文并非该 2005 方法的独立验证。',
 'gaps':'没有给任何建筑普适的 CQC 偏差百分比，也没有证明所有桥梁都只有两模态。',
 'scope':'检视 PDF 第 1–32 页章节，重点阅读第 1–3、13–19、20–32 页的论证/案例/结论；第 33–36 页参考文献未逐条读，公式图表尚未视觉逐项核对。'},
'KA-0475':{
 'problem':'1981 年单作者技术短文检验高楼高阶模态对位移、加速度、jerk 的贡献是否同样可以忽略。',
 'claims':[
 (1,'位移的一阶模态主导不保证加速度和 jerk 亦可忽略高阶模态。','The higher modes of vibration have an insignificant contribution to the displacement response; however their influence on the higherderivatives ofresponse, i.e., acceleration andjerk, is quite significant (2,4).'),
 (5,'在本文轻阻尼窄带模型及算例下，舒适/使用性判断应保留高阶模态，不能只凭位移一阶主导。','However, the assessment of serviceability and occupant comfort criteria requires the inclusion of higher modes of vibration in the dynamic analysis of tall buildings.'),
 (1,'在高楼居住舒适性问题上，忽略高阶模态会低估运动响应；该推论有结构/风场前提。','Therefore, occupant comfort in tall buildings can be affected by underestimating the dynamic response as a conse- quence of neglecting the higher modes of vibration.')],
 'limits':'第 1 页假设轻阻尼窄带结构，第 3 页忽略交叉项及固有频率邻域荷载谱缓变；第 4–5 页仅单个模型与特定简化谱比较，不能据算例将百分比推广到其他结构。',
 'relation':'博士论文 KA-0500 第 24 页讨论舒适性，此短文将服务性问题落实到高阶加速度；KA-0085 第 16 页另讨论局部效应截断，两者响应量不完全相同。',
 'gaps':'未提供任意高楼的高阶模态截断阈值；未核特定现代规范舒适限值。',
 'scope':'通读 PDF 第 1–6 页文字层，核对第 1 页前提、第 2–3 页推导条件、第 4–5 页表格和结论；第 5 页表值尚未对印刷图像逐项复核。'},
'KA-0119':{
 'problem':'1986 年单作者文以迎风/背风压力时空相关的实测检验顺风准定常/条带理论合成总体荷载时的简化。',
 'claims':[
 (4,'迎风与背风某对测点的互谱只代表部分区域，不能据此覆盖有分离涡峰值的角部。','However, one should not overlook the fact that the co-spectrum for taps 1 and 7, on one hand, does represent a major portion of the pressure fluctuations on the windward and leeward faces, but fails to incorporate the regions near the corners, which are characterized by distinct peaks associated with vortex shedding.'),
 (5,'迎风压力与远场风速谱近似线性转换存在高频衰减的条件。','At higher reduced frequencies, this trend may gradually diminish.'),
 (5,'若多个简化偏差方向相反，总荷载表面吻合也不能证明每一项模型假设成立。','It appears that various^assumptions made in the development of the alongwind loading may have some individual shortcomings; however, the overall load description may be quite satisfactory.')],
 'limits':'研究用模拟郊区边界层中高楼模型及选定测点/频率区间；第 5 页并不保证不同流场、几何的偏差总会抵消。原文第三句含 OCR 的 ^，保留原貌。',
 'relation':'与 KA-0561（2009，第 2 页）准定常应用边界相容，1986 实测只覆盖所测顺风压力场，不足以独立证实瞬变下击暴流。',
 'gaps':'没有通用的迎风/背风相关折减系数，也未给横风扭转的完整数值设计规范。',
 'scope':'阅读 PDF 第 1–5 页方法、谱图图注、结果和结论；图 1–3 的曲线坐标尚未逐点人工数字化。'},
'KA-0215':{
 'problem':'1988 年单作者文章把极端风、气动、结构动力参数的不确定性带入响应估计，以烟囱蒙特卡洛算例演示。',
 'claims':[
 (3,'把不确定来源分别列为风环境/气象、风—结构作用和结构性质，而非只给一个统一“安全系数”。','The parameters are broadly classified into three categories: (a) wind environment and meteorological data, (b) parameters reflecting wind-structure interactions, and (c) structural properties.'),
 (7,'当样本数量受限时可考虑方差缩减，不把算例的模拟次数当通用阈值。','The sampling error introduced by limited sample size may be improved without increasing the sample size by utilizing variance reduction techniques, e.g., importance sampling, antlthetic varlates, conditional expectations and strati- fied sampling (2, 32, 34).'),
 (8,'烟囱算例结果指向改进风—结构相互作用、模态频率/阻尼预测及极端风变异性刻画的需要。','The COVs for both compo- nents of response suggest a need for further improvement in the modeling of wind-structure interaction, prediction of natural frequencies and damping, and a reduction in the variability of extreme wind estimates.')],
 'limits':'第 6–7 页 598 ft 混凝土烟囱示例、给定分布与采样规模是演示，不是所有结构误差预算；第二摘句含 OCR 断词和拼写，必须回印刷页再引用。',
 'relation':'与 KA-0156（1987，第 1、22 页）可靠度框架同向，本文具体分解不确定性并演示传播，不提供对 2020 年 CFD 模型误差的量化。',
 'gaps':'没有给各类现代建筑统一的阻尼、风速或模型形式不确定度数值。',
 'scope':'阅读 PDF 第 1–8 页各段与方法例子及结论；第 9 页为参考文献；第 5–7 页表值未逐格视觉重开。'},
'KA-0346':{
 'problem':'2019 年 Kareem 等的第一作者论文尝试将 Davenport 风荷载链改为非平稳时频框架，考察准定常近似与时域实现。',
 'claims':[
 (10,'时频域准定常求解有计算效率优势，但牺牲捕捉瞬变效应的精度。','The solution of nonstationary wind-induced response in the time- frequency domain using the quasi-stationary assumption enables high computational efficiency, but sacrifices the accuracy of cap- turing transient effects.'),
 (10,'提出的链条旨在兼容非平稳与平稳风事件；这是作者提出的研究方向，不是已经进入规范的声明。','The generalized wind loading chain aims at facilitating seam- less response analysis under nonstationary as well as stationary wind events.')],
 'limits':'以数值示例说明两种时频表征，第 10 页明说准定常牺牲瞬变精度；未把方法的效率宣称成任意非平稳过程都精确。文中提及 Kwon/Kareem 2009、2013 GFF 是对既有合作成果的引用。',
 'relation':'与 KA-0561（2009，第 11 页）对非平稳设计荷载的挑战同向，2019 文提出可实现的时频链条，但非十年后对所有风型已“解决”。',
 'gaps':'不能推出不同事件的通用平均窗口、GEF 数字或法规已采纳此链条。',
 'scope':'检视 PDF 第 1–10 页引言、链条/示例和总结；图表公式只经文字层定位，未逐图校对，故为定向阅读草稿。'}
}
def norm(s):
 s=re.sub(r'(?<=\w)-\s+(?=\w)','',s)
 s=re.sub(r'\s+([,.;:!?])',r'\1',s)
 return re.sub(r'\s+',' ',s).strip()
validated=0
for key,entry in DATA.items():
 r=ROWS[key]; p=pathlib.Path(r['local_pdf_path'].split(';')[0]); assert p.is_file(),p
 pages=subprocess.run(['pdftotext','-raw',str(p),'-'],capture_output=True,text=True,check=True).stdout.split('\f')
 blocks=[]
 for page,zh,quote in entry['claims']:
  assert page>=1 and page<=len(pages), (key,page)
  assert norm(quote) in norm(pages[page-1]),(key,page,quote)
  assert len(re.findall(r'[.!?](?:\s|$)',quote))<=1,(key,quote)
  blocks.append(f'- {zh}（PDF 物理第 {page} 页）\n  > {quote}')
  validated+=1
 text=f'''# {key} 立场卡（续读工作稿）

① 文献与层：{r['title']}（{r['year']}）；{r['archive_id']} / {r['work_id'] or '无旧 work_id'}；索引层 {r['tier']}，署名位置 {r['kareem_position']}。实际首页作者、年份以 PDF 为准；元数据分层不等于实际撰稿人证明。PDF {len([x for x in pages if x.strip()])} 个文字页。
PDF：`{p}`；SHA-256：`{hashlib.sha256(p.read_bytes()).hexdigest()}`。

② 面对的问题：{entry['problem']}

③ 立场/建议（每段都需结合所标页的前提，不把被引他人实验据为 Kareem 原创）：

{chr(10).join(blocks)}

④ 原文局限、警告和归属：{entry['limits']}

⑤ 与其他时期的关系：{entry['relation']}

⑥ 未回答：{entry['gaps']}

阅读范围与未核材料：{entry['scope']}
'''
 out=ROOT/'cards'/f'{key}.md'
 if out.exists():
  assert out.read_text(encoding='utf-8')==text, f'Existing result differs: {out}'
 else:
  out.write_text(text,encoding='utf-8')
print('new_cards',len(DATA),'quotes_checked',validated)
