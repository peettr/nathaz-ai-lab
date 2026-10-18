#!/usr/bin/env python3
"""Conservative provenance checks; lexical matches do NOT equal scientific accuracy."""
import csv,re,sqlite3,collections,json,sys
from pathlib import Path
R=Path('./22_Lab/06_Logs/fulltext_kb')
TAG=sys.argv[1] if len(sys.argv)>1 else ''
c=sqlite3.connect('file:./ftkb/index.sqlite?mode=ro',uri=True)
source=list(csv.DictReader((R/('downburst_profiles_sample'+('_'+TAG if TAG else '')+'.csv')).open()))
fields=['source_type','z_max','U_max','normalization','profile_model','model_parameters','r_over_D','figure_table']
manual={('HIUJLEHZ','model_parameters'):'正确：p13 原文同句 C1=1.52 C2=0.68 n=1/6.5；不可把旁边 Wood 参数混用',('HIUJLEHZ','r_over_D'):'正确：p13 拟合范围 r/D=0.75,1,1.25,1.5,2,2.5,3',('HIUJLEHZ','normalization'):'正确：p13 Um 与 b 的文字定义',('HIUJLEHZ','figure_table'):'正确：p13 Fig 9a 和 Eq16',('FFREEQCW','r_over_D'):'正确：p10 Fig9 图注列四个位置',('R5RKQGYZ','z_max'):'正确：p9 近地最大径向速度高度 Z/D≈0.06',('R5RKQGYZ','normalization'):'正确：p9 b≈170mm、Vr/Vr,max 与 z/b',('YLMGJNCV','r_over_D'):'正确：p3 Fig2 标注 r/D=1.53',('SAI7PQLC','z_max'):'错误：p2 的 almost 80m 是 Hjelmfelt(1988) 的引述，不能当本文实测',('EFT4W6FE','U_max'):'不成立：p3 有多个 r/D，Vr/Vjet≈1 不能作为统一 Umax 且无对应高度'}
if TAG=='v2':manual={
 ('6X6ZP3YD','z_max'):'正确：p6 最大速度约 6m/s 对应离地 25mm',
 ('6X6ZP3YD','U_max'):'正确：p6 最大速度约 6m/s 对应离地 25mm',
 ('GBK98YNH','z_max'):'正确：p8 Fig3 峰值风速廓线最大值在5mm，即 Z/D=0.17',
 ('NXSSET4J','z_max'):'正确：工作站 写明峰时 Zmax=0.099m；是模拟监测点情境',
 ('NXSSET4J','r_over_D'):'有保留：工作站 分别写 R/D=1.0,1.4 与 1.37，模型合并到同字段但不说明各图对应',
 ('KN57R2JT','U_max'):'正确：p24 写 CM1-Case1 峰时 Up,max=47m/s',
 ('KN57R2JT','r_over_D'):'错误：p24 r/D=1.37 处提到不超10m/s，不能与 Up,max=47m/s 当作同一廓线位置',
 ('WZN3ETI3','z_max'):'有保留：p4 25–100m 是假设模型 Zmax 扫描范围，不是实测峰高',
 ('DWLQF7C3','z_max'):'有保留：p13 表3列 zm=25,50,75,100m 情景，不是单个观测值',
 ('L5B82XJJ','z_max'):'有保留：p9 205.69mm 是 upstream 某时刻鼻型廓线的高度，另一位置539.9mm 不可并作统一 zmax',
 ('EJXIIHA8','U_max'):'有保留：p7 表2多工况 U_z,max 两列含峰与平均、模型和足尺，未标每个值属于哪列时不能直接入库',
 ('JKAYZE37','z_max'):'有保留：p9 z/D=0.04 为特定粗糙度的峰高且OCR双栏交错，需对照原排版确认'}
out=[]
for x in source:
 text=c.execute('select text from pages where key=? and page=?',(x['key'],x['page'])).fetchone()[0]
 for fld in fields:
  val=x[fld]
  if not val:continue
  nums=re.findall(r'\d+(?:\.\d+)?',val)
  hits=sum(bool(re.search(r'(?<!\d)'+re.escape(y)+r'(?!\d)',text)) for y in nums)
  lexical='数字全见于原页' if nums and hits==len(nums) else '数字部分或全部未见' if nums else '非数值须人工判断'
  note=manual.get((x['key'],fld),'未人工核语义；数字共现不等于正确归属')
  out.append(dict(key=x['key'],pdf_page=x['page'],field=fld,model_value=val,numeral_count=len(nums),numerals_found=hits,lexical_check=lexical,manual_reviewer='Hermes 实验室助手' if (x['key'],fld) in manual else '',manual_note=note,source_pdf=x['pdf']))
with (R/('profile_verification'+('_'+TAG if TAG else '')+'.csv')).open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
print('atomic',len(out),'manual',len(manual),'numeric_all_matched',sum(x['numeral_count']>0 and x['numerals_found']==x['numeral_count'] for x in out),'manual errors',sum(x['manual_note'].startswith(('错误','不成立')) for x in out))
