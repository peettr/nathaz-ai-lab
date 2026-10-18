#!/usr/bin/env python3
"""Freeze paraphrased, title-anchored discovery questions before retrieval."""
import hashlib,json,sqlite3,os
from pathlib import Path
R=Path('./22_Lab/06_Logs/fulltext_kb')
# Each prompt is a human-authored paraphrase of a title/abstract, not a verbatim PDF sentence.
qs=[
('26GJD4SL','哪项工作利用 WindEEE Dome 定量刻画下击暴流风场？','下击暴流'),
('3TCRNYHI','哪项研究借助观测驱动的方法合成足尺下击暴流风速？','下击暴流'),
('5KSVNWQX','哪篇研究同时采用实验与数值方式模拟雷暴下击气流？','下击暴流'),
('7JPT33NW','哪项研究用冷源方法改进工程用下击暴流外流模拟？','下击暴流'),
('9XU7WRLP','哪项数值工作讨论地形对下击暴流风场的影响？','下击暴流'),
('CUXJF8GS','哪篇论文比较静止和移动风暴的冲击射流下击暴流数值风场？','下击暴流'),
('YTVL2E3G','哪项试验使用主动控制多叶片装置再现下击暴流样流动的演化？','下击暴流'),
('ZI3LRRBZ','哪项研究比较冲击射流与冷源两种微下击暴流模型？','下击暴流'),
('J85NJZX5','哪项参数研究聚焦线状下击暴流的近地外流？','下击暴流'),
('98I2UL3M','哪篇论文评估微下击暴流模型用于下降气流估算？','下击暴流'),
('AW5EFDWH','哪项研究给出轴对称微下击暴流的解析下降气流模型？','下击暴流'),
('253I3MP3','哪篇论文利用大涡模拟研究边界层中高层建筑极值风荷载？','高层风压'),
('2P8G7IQH','哪项研究探讨以 LES 作为高楼风荷载设计工具？','高层风压'),
('HXYJJE2L','哪项研究以验证过的大涡模拟和试验分析高层屋面峰值压力？','高层风压'),
('IXCVSP3L','哪篇研究以 CAARC 建筑为基准寻找高楼风荷载 CFD 标准设置？','高层风压'),
('9SBDC26T','哪篇论文使用变换过程来建模低层建筑风压？','风压'),
('B7HEEC89','哪项研究用高斯过程回归插值风压分布？','风压'),
('BTXIM4IJ','哪篇论文评估改进的随机流生成方法预测孤立建筑非定常风压？','风压'),
('DGQC6QDE','哪项工作研究非高斯风压极值估计中的矩匹配变换偏差和抽样误差？','风压'),
('IAMB6WBJ','哪项研究提出分析低层建筑围护构件压力测点数据的方法？','风压'),
('JUI6PMMH','哪篇研究将低层建筑墙面局部风压与美日设计规定比较？','风压'),
('9EQGPXLZ','哪项大涡模拟研究用于定义飓风边界层的谱与相干特征？','风谱'),
('J7Z8DSX8','哪篇论文推导风响应谱的理论定义？','风谱'),
('RFVUGP4Q','哪项研究重新讨论强风阵风谱与 von Karman 公式？','风谱'),
('ZCSZ8NMP','哪项研究采用演化波数频率联合谱模拟二维非均匀脉动风速？','风谱'),
('ARBF5DX3','哪篇论文提出大涡模拟通用入口湍流生成器？','CFD'),
('25NNYIQC','哪项研究比较中性边界层在不同地表粗糙度下的三种 LES 入流方法？','CFD'),
('YF9ABFIY','哪项新入流湍流生成器研究以标准高层建筑 LES 风效应为评估对象？','CFD'),
('IBDT2BIQ','哪篇研究以低层建筑的风荷载与结构响应检验大涡模拟？','结构响应'),
('M446G53T','哪项工作以 CFD 代理模型评估流线型桥梁截面形状变化的气弹效应？','结构响应'),
('QHHAB9IU','哪篇综述讨论 CFD 实际用于确定高层建筑风荷载？','CFD'),
('7YYNUDPT','哪项研究采用自适应克里金优化有不确定性的高层建筑舒适度？','结构响应')]
c=sqlite3.connect('file:./ftkb/index.sqlite?mode=ro',uri=True)
wiki=Path('./16_PETW/05_Literature_Wiki/wiki')
cardkeys=set()
for root,dirs,files in os.walk(wiki):
    for f in files:
        if f.endswith('.md') and 'papers' in root:cardkeys.add(f[:8].upper())
out=[]
for idx,(key,q,topic) in enumerate(qs,1):
    row=c.execute('SELECT title,pdf FROM pages WHERE key=? AND page=1 LIMIT 1',(key,)).fetchone()
    if not row:raise Exception('missing PDF page 1 '+key)
    out.append(dict(id=f'Q{idx:02d}',question=q,answer_key=key,answer_page=1,answer_title=row[0],answer_pdf=row[1],topic=topic,card=key in cardkeys,gold_evidence='PDF 第1物理页的标题及摘要；问题为人工转述，偏向首页的论文识别题'))
p=R/'questions.jsonl'
with p.open('x') as f:
 for a in out:f.write(json.dumps(a,ensure_ascii=False)+'\n')
print(len(out),'cards',sum(x['card'] for x in out),'noncards',sum(not x['card'] for x in out),'sha256',hashlib.sha256(p.read_bytes()).hexdigest())
