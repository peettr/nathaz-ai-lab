#!/usr/bin/env python3
"""Secondary local semantic triage of original 97 fields, not a human audit.
Judgments were assigned while reading the local PDF-page snippets; no invented human time.
"""
import csv,re,sqlite3
from pathlib import Path
R=Path(__file__).resolve().parent.parent
src=list(csv.DictReader((R/'profile_verification_v2.csv').open()))
# 1-based row numbers from immutable v2 source; avoid the bibliography-only 49-52.
ids=list(range(1,49))+list(range(53,83))
errors={10:'结构响应研究所用Wood经验公式，不是该研究的风洞实测来源',32:'示意图不是廓线数据来源类型',33:'Fig.1b为示意图，不是数据廓线',36:'Fig.3为网格无关性图，不能直接当独立物理廓线',67:'Fig.5为竖向速度而非所求径向/水平风速廓线',72:'OCR字符&不可解释为确定的峰值高度'}
qualified={
 8:'R/D=1.0与1.4属不同角度/曲线，1.37为峰值径向位置；不可合成单廓线',
 11:'25–100 m为假设模型扫描，不是实测z_max',
 14:'Wood模型参数与扫参/测站高度混列，须拆分',
 18:'Wood为被对照的他人公式，非本实验拟合模型',
 21:'outer scaling仅特定x/b区间，不可泛化全实验',
 26:'r/D=1仅指定空场剖面，需注明工况',
 29:'z_m为四个仿真情景参数，并非一次观测峰高',
 30:'四组为情景模型参数，不是连续廓线单个参数',
 31:'所列多个表图含结构响应，并非全部展示廓线',
 38:'x=D可对应r/D=1，但需保留方位和时刻',
 39:'Fig.10a需区分LES径向速度和Fig.10b瞬时场',
 41:'25mm与约6m/s同属该模拟工况，不能归作风洞测值',
 43:'Fig.15为模拟结果，需核具体面板才可归入廓线',
 45:'上游/中心两个z峰值对应不同index和工况，不是一条廓线',
 46:'14%是比中心参考峰值的相对增幅，绝对Umax未给',
 54:'z/D约0.04对应指定粗糙度，非所有工况',
 56:'1.0和1.2两处径向位置，不能合并一条曲线',
 59:'是与龙卷风峰值高度相比的倍数，非绝对zmax',
 64:'zmax是归一化符号，未提供数值',
 65:'V帽是全流场慢变径向速度峰值的符号而非数字',
 66:'归一化标尺随径向位置/工况变化，需保留定义',
 69:'Fig.3参考场与本风洞实验的归一化比较，需注明量和位置',
 73:'高度归一化用半峰高度b，不是峰值高度zmax',
 76:'5mm及Z/D=0.17需限定脉冲射流工况',
 77:'Z/D无量纲，不能把5mm当通用物理高度',
 80:'47m/s为CM1-Case1峰值时刻，不是全部径向剖面共同峰值',
 81:'r/D=1.37位置的数值不应与47m/s强行配对',
}
# Ensure every adjudication has a concrete reason and belongs to the selected set.
assert set(errors|qualified)<=set(ids)
c=sqlite3.connect('./ftkb/index.sqlite')
rows=[]
for i in ids:
 x=src[i-1];k=x['key'];p=int(x['pdf_page']);t=c.execute('select text from pages where key=? and page=?',(k,p)).fetchone()
 assert t,(i,k,p)
 text=t[0];v=x['model_value'];tokens=[已隐去]'[A-Za-z][A-Za-z0-9/-]{3,}|\d+(?:\.\d+)?',v)
 m=next((re.search(re.escape(tok),text,re.I) for tok in tokens if len(tok)>3),None)
 if m is None: m=next((re.search(re.escape(tok),text,re.I) for tok in tokens),None)
 excerpt=re.sub(r'\s+',' ',text[max(0,m.start()-75):m.end()+135]) if m else re.sub(r'\s+',' ',text[:190])
 status='错误' if i in errors else '有保留' if i in qualified else '同页语义支持（未核图像）'
 reason=errors.get(i) or qualified.get(i) or '字段与原页文字/图注同页对应；仅此页核查，不证明其他页无遗漏'
 rows.append(dict(v2_field_row=i,key=k,pdf_page=p,field=x['field'],model_value=v,status=status,semantic_reason=reason,source_excerpt=excerpt,reviewer='Hermes 实验室助手（AI人工逐条读页；非人类核查）',human_verifier='',human_seconds='',figure_condition='未独立逐曲线图读',source_pdf=x['source_pdf']))
assert len(rows)>=60
out=R/'profile_semantic_triage_round2.csv'
with out.open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
from collections import Counter,defaultdict
for field in sorted(set(r['field'] for r in rows)):
 z=[r for r in rows if r['field']==field]
 print(field,len(z),dict(Counter(r['status'] for r in z)))
print('TOTAL',len(rows),dict(Counter(r['status'] for r in rows)),out)
