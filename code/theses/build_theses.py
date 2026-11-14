#!/usr/bin/env python3
"""Read-only reconciliation of candidate degree works against the local page index."""
import csv, sqlite3, re, os
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parent
KB=sqlite3.connect('file:./services/ftkb/data/index.sqlite?mode=ro',uri=True)
KB.row_factory=sqlite3.Row
# Evidence phrases are copied from the indicated physical PDF page in the local full-text index.
# Desktop origin is remote; n_pages is the index's extracted page count, not a fresh PDF open.
works=[
 dict(student='Ahsan Kareem',year='1978',degree='Ph.D.',title='Wind Excited Motion of Buildings',university='Colorado State University',keys=['2F6RHVB9'],where='Zotero 2F6RHVB9; third EndNote offset-1121377; inventory KRM-0025',role='本人博士论文（非被指导学生）',page=1,quote='Submitted by Ahsan Kareem',confidence='已证实'),
 dict(student='Ahsan Kareem',year='1975',degree='M.S.（元数据）',title='Reduction of Wind Induced Motion of Tall Buildings',university='University of Hawaii（Zotero 元数据）',keys=['H3JY32PG'],where='Zotero H3JY32PG; inventory KRM-0023',role='本人硕士论文候选；无全文，不能核扉页/版本',page='',quote='',confidence='疑似'),
 dict(student='Lijuan Wang',year='2007',degree='Ph.D.',title='Stochastic Modeling and Simulation of Transient Events',university='University of Notre Dame',keys=['DSK-159ff747922a38ed'],where='ftkb DSK-159ff747922a38ed; I盘 dissertation/WangL122007.pdf',role='致谢自称 advisor；ND 目录 Research Director 另列 Joseph M. Powers，待核制度口径',page=14,quote='my advisor, Dr. Kareem',confidence='已证实'),
 dict(student='Gang Mei',year='2001',degree='Ph.D.',title='Model Predictive Control Schemes for the Mitigation of Natural Hazards: Theoretical and Experimental Studies',university='University of Notre Dame',keys=['DSK-372ab4e2d31f0f4e','DSK-d5f92fb61c4140c6'],where='ftkb DSK-372ab4e2d31f0f4e; DSK-d5f92fb61c4140c6; I盘 PhD_Dissertation',role='致谢 advisor',page=19,quote='my advisor, Professor Ahsan Kareem',confidence='已证实'),
 dict(student='Swaroop Krishna Yalla',year='2001',degree='Ph.D.',title='Liquid Dampers for Mitigation of Structural Response: Theoretical Development and Experimental Validation',university='University of Notre Dame',keys=['DSK-b1307155c817647e'],where='ftkb DSK-b1307155c817647e; I盘 PhD_Dissertation',role='致谢 advisor（扫描 OCR 将 Ahsan 识别为 Ansan）',page=20,quote='my advisor and guru, Prof. Ansan Kareem',confidence='已证实'),
 dict(student='Tracy Lynn Kijewski-Correa',year='2003',degree='Ph.D.',title='Full-Scale Measurements and System Identification: A Time-Frequency Perspective (Volume II)',university='University of Notre Dame',keys=['DSK-9e87b9f1090fa66e'],where='ftkb DSK-9e87b9f1090fa66e; I盘 Kijewski-Correa_v2.pdf (仅卷二)',role='扉页 Director（未见卷一及明确 advisor 致谢）',page=1,quote='Ahsan Kareem, Director',confidence='疑似'),
 dict(student='Devin A. Brown',year='2003',degree='M.S.',title='Analysis of Wind-Induced Acceleration and Pressure Data from an Eight-Hundred-Foot Building',university='University of Notre Dame',keys=['DSK-8468bddc87056f56'],where='ftkb DSK-8468bddc87056f56; I盘 dissertation/etd.pdf',role='扉页 Director Graduate Program；致谢仅感谢指导，未明确 advisor',page=1,quote='Ahsan Kareem, Director Graduate Program in Civil Engineering and Geological Sciences',confidence='疑似'),
]
# Source quotes must be present on the cited physical page, modulo whitespace; do not fabricate anchors.
for x in works:
 key=x['keys'][0]
 if not x['page']:
  x['pdf_pages']='';x['has_fulltext']='否';continue
 r=KB.execute('select text from pages where key=? and page=?',(key,x['page'])).fetchone()
 assert r and re.sub(r'\s+',' ',x['quote']) in re.sub(r'\s+',' ',r['text']),(key,x['quote'])
 att=KB.execute('select n_pages,pdf from attachments where key=? limit 1',(key,)).fetchone()
 assert att,(key,'no attachment')
 x['pdf_pages']=att['n_pages'] or ''
 x['has_fulltext']='是'
cols=['student','year','degree','title','university','in_library','library_where','has_fulltext','pdf_pages','kareem_role','evidence_page','evidence_quote','confidence']
with (ROOT/'theses_in_library.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,cols);w.writeheader()
 for x in works:w.writerow(dict(student=x['student'],year=x['year'],degree=x['degree'],title=x['title'],university=x['university'],in_library='是',library_where=x['where'],has_fulltext=x['has_fulltext'],pdf_pages=x['pdf_pages'],kareem_role=x['role'],evidence_page=x['page'],evidence_quote=x['quote'],confidence=x['confidence']))
# Directory metadata is not a PDF page; retain leads in the report, not in the proven-missing CSV.
with (ROOT/'not_in_library.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.writer(f);w.writerow(['student','year','degree','title','university','catalog_url','evidence_page','evidence_quote','confidence'])
# One external catalog entry explicitly contradicts treating program signatory alone as an advisor.
print('records',len(works),'confirmed incl own',sum(x['confidence']=='已证实' for x in works),'suspected',sum(x['confidence']=='疑似' for x in works))
print('physical page quote checks',sum(bool(x['page']) for x in works),'/',sum(bool(x['page']) for x in works))
print('page counts',[(x['student'],x['pdf_pages']) for x in works])
