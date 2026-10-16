import pathlib,json,collections,csv,hashlib,re
root=pathlib.Path(__file__).parent
q={x['id']:x for x in map(json.loads,(root/'questions_blind.jsonl').read_text().splitlines())}
r=[json.loads(x) for x in (root/'results.jsonl').read_text().splitlines()]
assert len(r)==30 and len(set(x['id'] for x in r))==30
assert hashlib.sha256((root/'questions_blind.jsonl').read_bytes()).hexdigest()==(root/'freeze.sha256').read_text().split()[0]
# One byte-identical cross-library copy has a translated Zotero title, which automatic matching missed.
duplicate={'END-5c6650f021459749':'./Zotero/storage/HUZ2C9E3/台风风场模型研究综述.pdf'}
a=pathlib.Path(q['R3-09']['source_pdf']); b=pathlib.Path(duplicate[q['R3-09']['source_key']]); assert hashlib.sha256(a.read_bytes()).digest()==hashlib.sha256(b.read_bytes()).digest()
reasons={'R3-01':'页错：正确中文综述仅返回首页、页2/9','R3-09':'字节相同跨库副本，自动标题匹配漏记，人工校正命中','R3-10':'字节相同跨库副本，自动标题匹配漏记，人工校正命中','R3-14':'未召回：原中文题翻译/语义匹配不足，显式英文问题诊断可命中同作第8页','R3-17':'页错：正确论文第13页入榜，但事实在第6页','R3-21':'未召回：书籍事实页未进前五','R3-23':'未召回：书籍事实页未进前五','R3-24':'未召回：书籍事实页未进前五','R3-28':'未召回：OCR 源页有识别文本；显式英文问题诊断可召回第30页，自动翻译/排序损失','R3-29':'页错：扫描书只命中第1页，事实在第140页，OCR 锚点仍存在','R3-30':'页错：扫描书只命中第4/5页，事实在第30页，OCR 锚点仍存在'}
out=[]
for x in r:
 y=dict(x); qq=q[x['id']]
 if qq['source_key'] in duplicate:
  for h in y['hits']:
   if h['source_pdf']==duplicate[qq['source_key']]:
    h['same_work']=True; h['page_hit']=abs(h['pdf_page']-qq['pdf_page'])<=1
 y['work_hit']=any(h['same_work'] for h in y['hits'])
 y['page_hit']=any(h['page_hit'] for h in y['hits'])
 y['reason']=reasons.get(x['id'],'命中' if y['page_hit'] else ('页错' if y['work_hit'] else '未召回'))
 y.pop('raw_output');y.pop('stderr')
 out.append(y)
(root/'adjudicated_results.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in out))
with (root/'group_metrics.csv').open('w',newline='') as f:
 w=csv.writer(f); w.writerow(['group','n','work_hit_at_5','work_and_physical_page_pm1_at_5'])
 for g in ['zh','zh2en','book','book_ocr','all']:
  sub=[x for x in out if x['group']==g or g=='all']
  w.writerow([g,len(sub),sum(x['work_hit'] for x in sub),sum(x['page_hit'] for x in sub)])
print([(g,len(s),sum(x['work_hit'] for x in s),sum(x['page_hit'] for x in s)) for g in ['zh','zh2en','book','book_ocr','all'] if (s:=[x for x in out if x['group']==g or g=='all'])])
print('failures',[(x['id'],x['reason']) for x in out if not x['page_hit']])
