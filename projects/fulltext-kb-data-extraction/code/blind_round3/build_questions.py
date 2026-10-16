import sqlite3,json,pathlib,re,hashlib,collections
out=pathlib.Path(__file__).parent
c=sqlite3.connect('file:./ftkb/index.sqlite?mode=ro',uri=True)
# group, key, physical page, paraphrased query, answer, page-local evidence anchor
items=[
('zh','N8U68UKD',4,'这篇入口湍流综述把人工生成法按机制分成哪四类？','谱合成、POD 重构、数字滤波、涡方法','人工合成法主要分为四类'),
('zh','N8U68UKD',8,'该中文入口湍流综述认为单一尺度合成涡在风谱方面有什么缺陷，提出何种多尺度方法？','单一涡尺度不能满足脉动风速功率谱；MSSEM 合成多尺度涡','因此不符合'),
('zh','9WK23VTL',6,'固体力学 AI4PDEs 综述里算子学习相对纯数据拟合的两项理论/泛化特点是什么？','有数学理论支持并具有离散不变性','离散不变性的优点'),
('zh','9WK23VTL',9,'该固体力学 AI4PDEs 综述怎样权衡强形式 PINN 与能量形式 PINN 的数值积分依赖和通用性？','强形式更通用且常不依赖数值积分；能量形式依赖积分方案、通用性较差','非常依赖数值积分'),
('zh','XERQ28BD',5,'神经算子湍流综述列出的 F-FNO 相对原版 FNO 的结构改动是什么？','因子化框架和跨层参数共享','跨层参数共享'),
('zh','XERQ28BD',9,'该中文湍流神经算子论文在瑞利泰勒算例中评价旋度演变时，检验了多少个大涡翻转时间？','3 个大涡翻转时间','3 个大涡翻转时间'),
('zh','Y9PBXS6X',5,'莫拉克水平混合敏感性试验中，增强混合使最大风速半径从弱混合的大约多少公里外移到 CS1 的多少公里？','约 140 km 到约 200 km','达到了 200 km'),
('zh','Y9PBXS6X',8,'莫拉克台风 CS0 与 CS1 对照里，登陆前风眼直径各约多少公里？','CS0 约120 km，CS1 约200 km','CS1 实 验 中 台 风 眼 的 大 小 约 200 km'),
('zh','END-5c6650f021459749',7,'台风风场中文综述介绍的 MASCOT 地形模型，输入高程和粗糙度的网格分辨率各是多少？','高程 50 m、粗糙度 100 m','分别为 50 m'),
('zh','END-5c6650f021459749',9,'这篇台风风险风场综述比对六种风险模型后，只有哪一个使用经验海陆转换系数？','RMS 模型','仅 RMS 模型'),
('zh2en','45AP3CPP',6,'台湾登陆台风的区域风速预报研究，在新竹、梧栖、高雄的特征筛选中设定的相关系数阈值是多少？','0.3','threshold CC was determined to be 0.3'),
('zh2en','VC6ELS7S',14,'高楼舒适度规范比较中，哪一个标准的阈值让 A、B 两栋楼在最保守组合下都无法通过？','NBR6123 (1988)','NBR6123, 1988'),
('zh2en','JUXVMPUC',8,'桑迪风暴灾后地形激光测量清单里，USGS 东新泽西灾后那次航测是哪几天？','2012-11-01 至 2012-11-05','November 1–5, 2012'),
('zh2en','END-9f99992b930de50b',8,'讨论意大利 La Spezia 非定常风记录的论文，图示风速仪采样率是多少？','10 Hz','sampling frequency is 10 Hz'),
('zh2en','END-23994f00e0223d1b',12,'Frederic 飓风登陆海岸风场对照中，观测合成和数值模型都把最大海岸风速放在风暴哪个象限？','前右象限','front right quadrant'),
('zh2en','6CIFJYXL',12,'重访简化飓风边界层模型的文章在 δ(R)=550m、最大切向风速70m/s时，解约在离中心多少公里处中断？','约 60 km','radius of about 60 km'),
('zh2en','ML5CFU3G',6,'5:1 矩形柱非定常加减速研究在测试的加速度范围里，阻力和升力系数是否出现超调？','两者都没有出现超调','displays an "overshoot" phenomenon'),
('zh2en','AQGQIIC7',33,'低层建筑风压 RANS 验证论文用哪些四个来流角检验空计算域的水平一致性？','0°、15°、30°、45°','(0°, 15°, 30°, and 45°)'),
('zh2en','8H9Q5TJU',17,'飓风涡度结构比较里，哪一种给定的径向压力廓线与观测结构最接近，其峰值约位于几倍最大风速半径？','EF 廓线，约 0.75 RMW','EF most clo-'),
('zh2en','END-67b90d1c06678623',9,'七个热带气旋的边界层方案试验中，哪种方案的路径偏差更大，而哪种最好？','MYJ 其次 ACM 偏差较大，BouLac 最佳','BouLac PBL physics'),
('book','WQD9DAF4',100,'《Wind Effects on Structures》讨论流体微元时，作用力分成哪两种物理来源？','重力体力与内部应力产生的表面合力','body force caused by gravity'),
('book','8NXTE4X2',93,'《Atmospheric Modeling, Data Assimilation, and Predictability》对初边值给得过少的情况，指出解会怎样？','解不唯一','solution will not be unique'),
('book','6EZT6DGI',160,'Kaimal 与 Finnigan 的边界层书在讨论局部涡扩散闭合时，哪两类非局部项不可忽略便会破坏局部通量与梯度的联系？','平流与湍流输运','advection and turbulent transport are negligible'),
('book','MHEB88AH',295,'《Design of Buildings for Wind》列的北美住宅楼十年重现期楼顶峰值舒适加速度建议区间是多少？','0.10–0.15 m/s²','0.10–0.15 m/s2'),
('book','55YKUQVN',100,'《Introduction to Dynamic Meteorology》解释水平流辐合怎样改变随体绝对涡度？','流体围成面积缩小，绝对涡度集中并增大','vorticity will be concentrated'),
('book','CT6G3Y7R',346,'《Wind Loading of Structures》解释独立雨棚下方堆料为何能改变底面压力符号？','堆料使底部气流部分或完全滞止，底面压力转正','positive pressures underneath'),
('book','KMYJYG7G',166,'《Numerical Methods in Weather Prediction》所述守恒律天气预报算法依靠哪一种拆分思路？','splitting-up method（分步/算子拆分）','splitting-up method'),
('book_ocr','7LUSTFFE',30,'Wilcox 扫描教材在讲涡量为何集中于小涡时，指出二维流动缺少什么机制？','涡伸长（vortex stretching）','Vortex stretching is absent in two-dimensional flows'),
('book_ocr','7BJLSXUD',140,'Dahlquist 与 Björck 扫描教材在计算余弦函数时，建议先将任意角折算到哪个象限的小区间再近似？','第一象限','in the first quadrant'),
('book_ocr','END-6f13b67d5f8013c8',30,'《热带气旋动力学引论》扫描页所述 Carla 台风相关台湾新寮单日降水纪录是多少毫米？','24 小时 1672 mm','1672mm'),
]
assert len(items)==30
ocr={r['canonical_key']:r for r in map(json.loads,open('./ftkb_ocr/page_manifest_dedup.jsonl'))}
rows=[]
for i,(group,key,p,q,a,anchor) in enumerate(items,1):
 if group=='book_ocr':
  m=ocr[key]; assert m['physical_page']!=p or True
  path=pathlib.Path('./ftkb_ocr/pages')/key/f'p{p:04d}.txt'; text=path.read_text(); pdf=m['source_pdf']; attachment=key; title=pathlib.Path(pdf).stem
 else:
  record=c.execute('select attachment,title,text,pdf,type from pages where key=? and page=? limit 1',(key,p)).fetchone(); assert record,(key,p)
  attachment,title,text,pdf,typ=record
  if group=='book': assert typ in ('book','bookSection'),(key,typ)
 # Literal anchor must be present on exactly the selected PDF physical page, not reference list.
 assert re.sub(r'\s+',' ',anchor).casefold() in re.sub(r'\s+',' ',text).casefold(),(key,p,anchor)
 assert p>1
 rows.append({'id':f'R3-{i:02d}','group':group,'question':q,'answer':a,'source_key':key,'attachment':attachment,'title':title,'pdf_page':p,'source_pdf':pdf,'evidence_anchor':anchor,'ocr':group=='book_ocr'})
qpath=out/'questions_blind.jsonl'
assert not qpath.exists(),'frozen question file already exists; never overwrite'
qpath.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
sha=hashlib.sha256(qpath.read_bytes()).hexdigest()
(out/'freeze.sha256').write_text(f'{sha}  questions_blind.jsonl\n')
print('FROZEN',len(rows),collections.Counter(r['group'] for r in rows),sha)
