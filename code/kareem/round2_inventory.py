#!/usr/bin/env python3
"""Idempotent local staging-PDF additions; preserves existing work IDs."""
import csv,re,subprocess
from pathlib import Path
from round2_candidates import EX
B=Path(__file__).parent
p=B/'inventory.csv';rows=list(csv.DictReader(p.open(encoding='utf-8-sig')));fields=list(rows[0]);by={x['work_id']:x for x in rows}
# Source titles and authors verified against PDF first pages; new works do not replace prior rows.
spec={
'04':('KRM-0021','PXRJNXFA','2015','The Wind Engineer / AAWE','Bernardini, E.; Bobby, S.; Spence, S. M. J.; Wei, D.; Kareem, A. [Kareem 第5作者]','','高层建筑气动与风振;桥梁气动与颤振;可靠度与性能化设计'),
'05':('KRM-0195','Y2R9SZST','2026','Advances in Wind Engineering','Hu, L.; Kareem, A. [Kareem 第2作者]','10.1016/j.awe.2025.100097','非平稳风与雷暴风;风荷载与试验方法'),
'06':('KRM-0198','45ZGKKUP','2011','Journal of Structural Engineering','Kwon, D. K.; Kareem, A. [Kareem 第2作者]','10.1061/(ASCE)ST.1943-541X.0000412','阵风因子与峰值因子;随机过程模拟与非高斯'),
'07':('KRM-0199','IJVHR8TV','2001','Journal of Structural Engineering','Zhou, Y.; Kareem, A. [Kareem 第2作者]','10.1061/(ASCE)0733-9445(2001)127:2(168)','阵风因子与峰值因子;高层建筑气动与风振;风荷载与试验方法'),
'08':('KRM-0200','CWMTBVI5','2004','Journal of Structural Engineering','Chen, X.; Kareem, A. [Kareem 第2作者]','10.1061/(ASCE)0733-9445(2004)130:10(1425)','高层建筑气动与风振;风荷载与试验方法'),
'09':('KRM-0201','DTWMZIUV','1996','Journal of Wind Engineering and Industrial Aerodynamics','Kareem, A.; Gurley, K. [Kareem 第1作者]','10.1016/0167-6105(96)00004-9','高层建筑气动与风振;结构控制与状态识别;可靠度与性能化设计'),
'10':('KRM-0202','ZJG9R4HA','2013','Journal of Wind Engineering and Industrial Aerodynamics','Kareem, A.; Wu, T. [Kareem 第1作者]','10.1016/j.jweia.2013.06.002','非平稳风与雷暴风;桥梁气动与颤振;随机过程模拟与非高斯'),
'11':('KRM-0203','39FRDPCX','2005','Journal of Engineering Mechanics','Chen, X.; Kareem, A. [Kareem 第2作者]','10.1061/(ASCE)0733-9399(2005)131:4(325)','随机过程模拟与非高斯;信号处理与数值方法'),
'12':('KRM-0204','QTTNCUKF','2012','Frontiers of Structural and Civil Engineering','Wu, T.; Kareem, A. [Kareem 第2作者]','10.1007/s11709-012-0179-1','桥梁气动与颤振'),
}
for short,(id,key,year,venue,authors,doi,topic) in spec.items():
 pg=int(re.search(r'Pages:\s*(\d+)',subprocess.run(['pdfinfo',str(EX[short])],capture_output=True,text=True,check=True).stdout).group(1))
 if id in by:
  x=by[id];x['library_item_ids']=';'.join(dict.fromkeys(filter(None,x['library_item_ids'].split(';')+[key])));x['libraries']=';'.join(dict.fromkeys(filter(None,x['libraries'].split(';')+['Zotero'])));x['has_fulltext']='是';x['pdf_pages']=str(pg)
  if not x['year']:x['year']=year
  if not x['venue']:x['venue']=venue
  if not x['authors'] or x['authors'].startswith('见 Zotero'):x['authors']=authors
  x['dedup_note']+='；阶段2第二轮本地合法 PDF 首页核验（只读）'
 else:
  title={'06':'Peak Factors for Non-Gaussian Load Effects Revisited','07':'Gust Loading Factor: New Model','08':'Equivalent Static Wind Loads on Buildings: New Model','09':'Damping in structures: its evaluation and treatment of uncertainty','10':'Wind-induced effects on bluff bodies in turbulent flows: Nonstationary, non-Gaussian and nonlinear features','11':'Proper Orthogonal Decomposition-Based Modeling, Analysis, and Simulation of Dynamic Wind Load Effects on Structures','12':'An overview of vortex-induced vibration (VIV) of bridge decks'}[short]
  x=dict.fromkeys(fields,'');x.update(work_id=id,title=title,year=year,venue=venue,authors=authors,doi=doi,library_item_ids=key,libraries='Zotero',has_fulltext='是',pdf_pages=str(pg),topic=topic,dedup_note='litwiki 合法补入；本地 PDF 首页核题名/作者',unpublished='否');rows.append(x);by[id]=x
with p.open('w',encoding='utf-8',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
print('inventory',len(rows),'staged',[(k,v[0]) for k,v in spec.items()])
