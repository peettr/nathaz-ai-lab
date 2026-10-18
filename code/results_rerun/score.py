import json,csv,re,collections,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent
qs=[json.loads(x) for x in (root.parent/'questions_blind.jsonl').open()]
rs={x['id']:x for x in (json.loads(line) for line in (root/'results.jsonl').open())}
assert set(rs)=={x['id'] for x in qs} and len(rs)==30
old={x['id']:x for x in (json.loads(line) for line in (root.parent/'results'/'adjudicated_strict.jsonl').open())}
rows=[]
for q in qs:
 r=rs[q['id']]; assert r['question']==q['question']
 names={x['windows'].casefold().replace('/','\\') for x in q['aliases']}
 names.add(q['windows_path'].casefold().replace('/','\\'))
 pages=[]; details=[]
 for h in r['hits']:
  source=h['source_pdf'].casefold().replace('/','\\')
  same=h['key'].casefold().startswith('dsk-'+q['sha256'][:16]) or source in names or (('同一作品另有' in h['block'][:450]) and ('DSK-'+q['sha256'][:16] in h['block'][:450]))
  # An explicit alias or exact desktop content hash is the only permitted equivalence here.
  if same: pages.append(h['pdf_page'])
  details.append({'rank':h['rank'],'key':h['key'],'same_work':same,'page':h['pdf_page']})
 matching=[h for h,d in zip(r['hits'],details) if d['same_work']]
 hit=bool(matching); pagehit=any(abs(x-q['pdf_page'])<=1 for x in pages)
 markers=[h for h in matching if h['source_pdf'].startswith('I:\\') and ('只在台式机能打开' in h['block'])]
 candidate=[h for h in matching if '题目候选' in h['heading']]
 hex_title=[h for h in matching if re.search(r'^<[0-9A-Fa-f]{16,}>',h['title'])]
 ocr_warning=[h for h in matching if 'OCR 文本，引用前核原页' in h['block'].split('引用时写')[0]]
 row={'id':q['id'],'group':q['group'],'work_hit':hit,'page_hit':pagehit,'same_work_pages':pages,'translation_fallback':r['translation_fallback'],'translated':r['translated'],'internal_deadline':r['internal_deadline'],'desktop_source_path':bool(markers),'candidate_title':bool(candidate),'hex_title':bool(hex_title),'ocr_warning':bool(ocr_warning),'matching_hits':details,'old_work_hit':old[q['id']]['work_hit'],'old_page_hit':old[q['id']]['page_hit']}
 rows.append(row)
(root/'adjudicated_strict.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows))
with (root/'group_metrics_strict.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['group','n','work_hit','page_hit','translated','translation_fallback','internal_deadline','old_work_hit','old_page_hit'])
 for g in ['book','literature','chinese','ocr','ALL']:
  a=[x for x in rows if g=='ALL' or x['group']==g]
  w.writerow([g,len(a)]+[sum(bool(x[k]) for x in a) for k in ['work_hit','page_hit','translated','translation_fallback','internal_deadline','old_work_hit','old_page_hit']])
with (root/'comparison_strict.jsonl').open('w') as f:
 for x in rows:
  x2={k:x[k] for k in ['id','group','work_hit','page_hit','old_work_hit','old_page_hit']}; x2['page_change']='变好' if x['page_hit'] and not x['old_page_hit'] else '变差' if x['old_page_hit'] and not x['page_hit'] else '不变'
  f.write(json.dumps(x2,ensure_ascii=False)+'\n')
print('metrics',collections.Counter((x['group'],x['work_hit'],x['page_hit']) for x in rows))
print('unmatched but possible alias')
for q in qs:
 r=rs[q['id']]; row=next(x for x in rows if x['id']==q['id'])
 if not row['work_hit']:
  print(q['id'],[(h['rank'],h['key'],h['title'][:65],h['pdf_page']) for h in r['hits']])
