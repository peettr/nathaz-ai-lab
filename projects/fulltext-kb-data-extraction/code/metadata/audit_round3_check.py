import csv,sqlite3,pathlib,collections,re
B=pathlib.Path(__file__).parent
D=sqlite3.connect('file:./ftkb_desktop/page_text_v2.sqlite?mode=ro',uri=True)
I=sqlite3.connect('file:./ftkb/index.sqlite?mode=ro',uri=True)
e={r['record_id']:r for r in csv.DictReader((B/'endnote_records_v3.csv').open())}
fail_desktop={'f0aecb1cf','783d0b4af','8a80a835b','55788268d'}
fail_end={'UNLINKED-c59d1f0a18e8','UNLINKED-b6026bd1d714'}
rows=[]
for r in csv.DictReader((B/'audit_round3_30.csv').open()):
 if r['stratum'].startswith('Desktop'):
  x=D.execute('select text from pages where sha256=? and physical_page=1',(r['id'],)).fetchone();first=' '.join(((x[0] or '') if x else '').split())[:360]
  key=r['id'][:9];bad=key in fail_desktop
  if key=='8a80a835b':reason='首页为会议摘要占位说明；PDF Info 标题未在本页正文核实'
  elif key=='55788268d':reason='首页题名还有“传感技术研究”；PDF Info 不完整'
  elif key=='f0aecb1cf':reason='PDF Info 为排版软件章节文件名，不是作品标题'
  elif key=='783d0b4af':reason='PDF Info 为 PowerPoint 生成文件名'
  else:reason='首页文字与题名可对应（仍非图像逐字核对）'
 else:
  x=e[r['id']];path=x['pdf_paths'].split(' | ')[0];p=I.execute('select text from pages where pdf=? and page=1',(path,)).fetchone();first=' '.join(((p[0] or '') if p else '').split())[:360]
  bad=r['id'] in fail_end;reason='未关联 ENL 且题名截断' if bad else 'ENL 题名与 PDF 首页文字可对应（未核原页图）'
 r['first_page_evidence']=first;r['usable']=int(not bad);r['assessment']=reason
 rows.append(r)
with (B/'audit_round3_checked_30.csv').open('w',encoding='utf8',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
print(collections.Counter((r['stratum'],r['usable']) for r in rows))
