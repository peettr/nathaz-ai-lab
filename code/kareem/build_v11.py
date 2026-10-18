#!/usr/bin/env python3
"""Apply the Lead's seven adjudications without altering v1 or the source CSV."""
from pathlib import Path
import re,csv,collections
B=Path(__file__).parent
raw=B.joinpath('Kareem_判断清单_v1.md').read_text()
rows={r['judgment_id']:r for r in csv.DictReader((B/'judgments_raw.csv').open(encoding='utf-8-sig'))}
heads=re.split(r'(?=^### KC-\d\d｜)',raw,flags=re.M)
pre=heads[0]; blocks={int(re.match(r'### KC-(\d+)',s).group(1)):s for s in heads[1:]}
assert set(blocks)==set(range(1,61))
# In each judgment, quote every source row used for a distinct substantive clause.
extra={10:['KJ-0193'],15:['KJ-0216'],21:['KJ-0265'],31:['KJ-0268'],38:['KJ-0066','KJ-0067'],48:['KJ-0230'],50:['KJ-0273'],53:['KJ-0156'],54:['KJ-0159'],58:[]}
claims={
1:'边界层风常用的平稳模型用于阵风锋时可能不适用，阵风锋可用时变参数描述。',
2:'截至 2019 年，非天气尺度风（non-synoptic wind）的阵风锋设计实践尚少明确方案，原因包括特征认识缺共识、可供证实的数据稀缺及非平稳时变过程难处理。',
4:'阵风锋规范化早期，严谨的概率廓线演化方案之外，单一廓线模型加阵风锋风速图调整可能更合适。',
7:'当非平稳风的瞬时统计特性变化很慢、脉动风气动相互作用的瞬态效应不显著时，准平稳假设可能适用。',
8:'该文转述并采纳 Chen（2008）和 Langley（1987）的判断：准平稳传递近似忽略结构动力传递函数的瞬态滞后，可能高估响应。',
10:'若将 2014 年讨论的 ASCE 7 基本风速调整到 3 秒移动平均，柔性结构 GEF 可保留原式，但阵风、平均风速和湍流强度廓线仍需仔细重审。',
11:'截至 2013 年，该文指出阵风锋设计中风速匹配准则的选择显著影响设计荷载，所涉定量描述的普遍共识仍在形成。',
13:'在该文跨规范比较中，以较长平均时距计算的峰值底部弯矩和位移 GLF，其规范间估计差异较小。',
15:'高层风致响应预测对结构动力特性尤其敏感，应将动力特性估计误差与风洞预测响应的误差分别归因。',
18:'对典型建筑运行风速对应的低折减风速范围，准定常理论不适用；该文认为气动阻尼评估必须基于非定常气动力学。',
21:'该文转述并采纳 Gurley 与 Kareem（1997）的讨论：有记忆的目标信号采用静态变换可能丢失记忆，Volterra 模拟所需核也未必可得。',
22:'POD 降阶表示须保留随机场及相关量的重要特征，或确认近似表示造成的改变可接受。',
25:'截至 2020 年，输入输出为随机场而非随机变量时，可靠稳健的代理模型开发仍是重大挑战。',
31:'桥梁运动诱导力的准定常理论忽略非定常流固耦合效应；也不能将所有运动诱导效应简单归为气动阻尼。',
32:'桥面 VIV 缩尺试验的无量纲振幅直接乘实际桥面尺寸所得的“等效”实桥振幅，鉴于 VIV 非线性可能值得质疑。',
35:'阻尼估计具有固有变异，增加正常使用极限状态评估的不确定性。',
37:'截至 2026 年，该文认为因缺少稳健且普遍接受的基准，PBWE 结果验证仍很困难，甚至可能不可行。',
38:'阻尼量化比其他结构力学特性更难，因为耗能机制复杂且数量多，不宜视作易确定的常数。',
39:'用低幅值风致响应识别阻尼时，应能区分信号噪声和真实响应。',
40:'在高层建筑或长跨桥的强风、地震等非平稳事件中，缺少长段平稳数据会使常规辨识方法可能无法可靠估计阻尼。',
41:'线性黏性阻尼比与振幅无关，库仑阻尼比随振幅反比变化，平方速度阻尼比则随振幅正比变化。',
42:'对含多个分离良好的模态的系统应用随机减量法时，应围绕目标模态带通滤波。',
44:'在该文的跨规范风荷载比较中，应采用相近平均时距进行结果比较。',
48:'为非平稳风选平均时距或可变平均方案，应兼顾保留高频功率谱与消除序列相关。',
50:'协方差矩阵 POD 的子过程仅在零时滞不相关，因此不能借逐过程独立模拟取得谱矩阵 POD 的效率优势。',
53:'评估张力腿平台风效应不能与其他低频荷载（如缓变波漂移）孤立开来。',
54:'线性自由面绕射理论限于小幅波；有限幅波需要考虑自由面非线性的绕射理论。',
55:'在该文张力腿平台等海洋结构的缓变黏性及势漂移力问题中，等效线性化虽能较准估计均方力，却不能反映缓变黏性力。',
58:'截至 2026 年，该文认为对大规模 TC-PBWE 模拟，WRF-ARW 一类模拟中的局地观测同化通常不可行。',
59:'截至 2026 年，LES 的高计算成本及其模拟整个 TC 的适合性争议限制了它当时在 PBWE 的适用性。',
60:'对线性化 TCBL 模型，该文建议用于 PBWE 前将计算需求与准确性同 KW01 模型严谨比较。',
}
# Do not present contextual qualifiers as verbatim statements unless a cited passage supports them.
context={
10:'原文物理第 6 页先说明“new, more accurate wind map based on a 3-s moving average”；以下两句均在该页。',
18:'物理第 8 页前文将适用情形限为典型建筑运行风速对应的低折减风速。',
58:'物理第 6 页上文所称 such data assimilation 为局地观测同化。',
60:'物理第 14 页前文讨论的是线性化 TCBL 模型。',
}
# For conditional clauses with no KJ source row, make a bounded literal excerpt from the SAME PDF page;
# preserve glyphs as extracted by pdftotext -raw and confirm in the document validator.
additional_literal={
 10:(6,'Currently, research has been conducted on the standardization of basic wind speeds using measured wind records with proper adjustments for appropriate modeling of, for example, averaging time, height, and exposure corrections (e.g., Masters et al. 2010; NIST 2012; Lombardo 2012; P. J. Vickery, personal communication, 2014), which would result, in the near future, in the establishment of a new, more accurate wind map based on a 3-s moving average.'),
 18:(8,'As noted earlier, the quasi-steady theory is generally not applicable in the low reduced velocity range applicable to the operational velocities of typical buildings in wind.'),
 58:(6,'Local data assimilation has been shown to improve the accuracy of TCBL simulations when compared with measurements.'),
 60:(13,'The KW01 model has several closely related formulations within the hierarchy of TCBL models, obtained through linearization and sum­ marized previously in Sections 3.1.4 and 3.3.'),
}
for i,b in blocks.items():
 if i in (6,28,47):continue
 if i in claims:b=re.sub(r'^### KC-\d\d｜.*$',f'### KC-{i:02d}｜{claims[i]}',b,count=1,flags=re.M)
 if i==2:b=b.replace('适用条件：非天气尺度风的规范设计。','适用条件：非天气尺度（non-synoptic）风中的阵风锋规范设计；限该文发表时。')
 if i==4:b=b.replace('而非过于复杂的概率廓线演化','而非概率廓线演化')
 if i==7:b=b.replace('仅缓慢演变且瞬态作用不显著','统计特性慢变、瞬态作用不显著时可能适用；非必要条件')
 if i==10:b=b.replace('以基本风速平均口径确实被调整为前提；2014 年 ASCE 7。','以基本风速改为 3 秒移动平均为前提；2014 年讨论的 ASCE 7，不自动适用于现行版。')
 if i==18:b=b.replace('气动阻尼的评估，不能泛化为所有结构阻尼。','典型建筑运行风速对应的低折减风速范围内的气动阻尼；非所有结构阻尼。')
 if i==25:b=b.replace('逐字摘句（KJ-0174）：','逐字摘句（KJ-0174；[OCR：摘句中的 “Field regressor” 为页内小标题，不属于正文句子]）：')
 if i==33:b=b.replace('逐字摘句（KJ-0190）：','逐字摘句（KJ-0190；[OCR：tinearization 应为 linearization，逐字保留提取文本]）：')
 if i==35:b=b.replace('适用性极限状态','正常使用极限状态')
 if i==41:b=b.replace('逐字摘句（KJ-0257）：','逐字摘句（KJ-0257；[OCR：tile 应为 the，逐字保留提取文本]）：')
 if i==42:b=b.replace('多个分离模态','多个分离良好的模态')
 if i==44:b=b.replace('跨规范比较必须统一风速平均时距','跨规范比较应采用相近平均时距')
 if i==55:b=b.replace('该文所讨论的波浪力响应；首页证据。','张力腿平台的缓变黏性与势漂移力；首页证据，不外推一般建筑。')
 if i==59:b=b.replace('整场 TC 的大规模 PBWE；不是所有局部 LES。','截至 2026 年的整场 TC / PBWE 适用性讨论；不否定局部 LES。')
 if i==60:b=b.replace('新 TCBL 模型用于 PBWE 之前。','该文讨论的线性化 TCBL 模型用于 PBWE 之前。')
 if i in (11,37,59):b=b.replace('演变/分歧：','演变/分歧：该状态仅为发表年份的判断；')
 if i in extra:
  lines=[]
  for kid in extra[i]:
   r=rows[kid];assert r['keep']=='是'
   lines.append(f'逐字摘句（{kid}，PDF 物理第 {r["pdf_page"]} 页）：“{r["quote_en"]}”')
  b=re.sub(r'(?=^适用条件：)', '\n'.join(lines)+'\n', b, count=1,flags=re.M)
 if i in additional_literal:
  pg,quote=additional_literal[i]
  b=re.sub(r'(?=^适用条件：)',f'逐字摘句（补充，PDF 物理第 {pg} 页）：“{quote}”\n',b,count=1,flags=re.M)
 if i==18:b=b.replace('为什么：原文未给理由。','为什么：原文将准定常理论不适用限定于该低折减风速范围。')
 if i in context:b=re.sub(r'(?=^适用条件：)',f'语境限定：{context[i]}\n',b,count=1,flags=re.M)
 blocks[i]=b
# Appendices retain IDs, but no longer counted as KC judgment entries.
removed={i:blocks[i].replace(f'### KC-{i:02d}｜',f'#### 原编号 KC-{i:02d}｜',1) for i in (6,28,47)}
regular={i:b for i,b in blocks.items() if i not in removed}
counts=collections.Counter()
for b in regular.values():counts[re.search(r'主题：([^；]+)',b).group(1)]+=1
single=sum('证据单一' in b.splitlines()[1] for b in regular.values())
front=sum(any(rows[k]['round']=='1' for k in re.findall(r'KJ-\d+',re.search(r'^出处：.*$',b,re.M).group())) for b in regular.values())
summary='；'.join(f'{k} {v}' for k,v in counts.items())
intro=(f'# Kareem 专业判断清单 v1.1（审查 4cea8880 裁决后修订稿）\n\n'
       '使用说明：这是保留作者、年份和适用范围的文献判断清单，不代表 Kareem 个人原创或长期有效的规则。引用他人判断之处标明转述；历史规范或模型状态不得自动外推。\n\n'
       f'正式条目 {len(regular)}；各主题：{summary}。证据单一 {single}；含 round=1 首页来源 {front}；附录 3 条不计入。编号 KC-06、KC-28、KC-47 保留但不复用。\n\n'
       '出处的 PDF 页均指物理页；[OCR] 为提取文本残字，未擅改逐字引文。原文未给的理由不外推；候选适用线不是项目采纳结论。\n\n')
body=raw.split('## 非平稳风与雷暴风',1)[1]
section_order=[]
for line in raw.splitlines():
 if line.startswith('## ') and not line.startswith('## 阶段'):section_order.append(line)
section_order=[x for x in section_order if x!='## 非平稳风与雷暴风']
section_order=['## 非平稳风与雷暴风']+section_order
out=intro
for sec in section_order:
 out+=sec+'\n\n'
 for i,b in regular.items():
  if re.search(r'主题：([^；]+)',b).group(1)==sec[3:]:out+=b.rstrip()+'\n\n'
out+='## 附录：背景、转述及案例（非正式判断）\n\n以下原编号不复用，不计入正式条目。KC-06 为 RFD 特定时段数据描述并转引 Orwig & Schroeder（2007）；KC-28 为本文方法描述；KC-47 为 2019 年研究动机/历史背景。\n\n'
for i in removed:out+=removed[i].rstrip()+'\n\n'
(B/'Kareem_判断清单_v1.1.md').write_text(out)
pack='# 审查包 v1.1（正式判断；每项仅判断、摘句、文献及 PDF 物理页）\n\n不含附录 KC-06、KC-28、KC-47；审查 4cea8880 裁决后修订。\n\n'
for sec in section_order:
 pack+=sec+'\n\n'
 for i,b in regular.items():
  if re.search(r'主题：([^；]+)',b).group(1)!=sec[3:]:continue
  pack+=b.splitlines()[0]+'\n'+re.search(r'^出处：.*$',b,re.M).group()+'\n'
  for x in b.splitlines():
   if x.startswith('逐字摘句'):pack+=x.replace('逐字摘句','摘句')+'\n'
  pack+='\n'
(B/'review_pack_v1.1.md').write_text(pack)
# Adapt the old exam WITHOUT silently retaining references to an appendix ID.
q=(B/'考题草稿.md').read_text().replace('专业判断考题草稿（待独立审查）','专业判断考题 v1.1（审查 4cea8880 裁决后）')
parts=re.split(r'(?=^## 题 \d\d)',q,flags=re.M); assert len(parts)==21
new=[]
for p in parts[1:]:
 n=int(re.match(r'## 题 (\d+)',p).group(1))
 if n==2:p=p.replace('后续可迭代','并非否定严谨概率方案')
 if n==3:p=p.replace('何时允许','在什么条件下可能适宜').replace('两个条件必须同时指出','说出慢变与瞬态不显著；不是“仅当”')
 if n==6:p=p.replace('若修改当时 ASCE 7 基本风速的平均时距','若将当时 ASCE 7 的基本风速改为 3 秒移动平均').replace('前提是基本风速确已调整','前提是基本风速调整到 3 秒移动平均')
 if n==9:p=p.replace('两类误差分别归因','两类误差应分开评估')
 if n==13:p=p.replace('Volterra 所需核也可能不可得','Volterra 所需核并非总可得（该文转述 Gurley 与 Kareem 1997）')
 if n==15:
  src=re.search(r'^出处：.*$',blocks[29],re.M).group()
  p=f'## 题 15（桥梁气动与颤振）\n题干：桥梁时域分析把自激力作准定常近似时，气动阻尼与响应各可能如何偏？\n标准答案：该文判断气动阻尼会被高估，继而响应低估；须限定为该自激力近似。\n判分要点：气动阻尼高估/响应低估；不能泛化到一切时域分析。\n{src.replace("出处：","出处：KC-29；",1)}\n难度：难。\n\n'
 if n==18:p=p.replace('耗能机制复杂众多','耗能机制复杂众多，且与其他力学特性相比更难估计')
 if n==20:p=p.replace('只保证零时滞不相关；不保证任意时滞，独立模拟优势丧失','只保证零时滞不相关；文中因此认为独立模拟的效率优势丧失')
 new.append(p)
q=parts[0]+''.join(new)
(B/'考题_v1.1.md').write_text(q)
changes=['# v1 → v1.1 改动表（审查 4cea8880）','',f'正式条目 60→{len(regular)}；附录 3，编号保留；20 道题保持 20 道。','']
for i in range(1,61):
 a=blocks[i];old=re.split(r'(?=^### KC-\d\d｜)',raw,flags=re.M)[i]
 if i in removed:desc='移至文末附录，不再作为正式判断。'
 elif i in claims:desc=f'判断改为「{claims[i]}」；逐字来源或语境条件同步调整。'
 elif a!=old:desc='术语、适用条件、逐字摘句或发表时状态调整。'
 else:continue
 rule=('4' if i in (6,28,47) else '1,2' if i in (10,15,21,31,38,48,50,53,54,58) else '2,3,5,6' if i in claims else '5,6')
 changes.append(f'- KC-{i:02d}｜裁决第 {rule} 条：{desc}')
changes+=['','考题：第 02、03、06、09、13、15、18、20 题同步调整；第 15 题以 KC-29 替换附录 KC-28（裁决第 7、4 条）。其余考题仍指正式条目。','核验：运行 validate_v11.py 与 validate_judgments.py；语义和排版仍需 Lead 阅读抽查。']
(B/'changes_v1.1.md').write_text('\n'.join(changes)+'\n')
print('formal',len(regular),'topics',dict(counts),'single',single,'front',front,'exam',len(new),'changed',len(changes))
