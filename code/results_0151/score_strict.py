import json, re, hashlib, collections
from pathlib import Path
root=Path(__file__).resolve().parent
base=root.parent
sha='8e08ae4bd5ba725e6dd2d2df80032e9ff35880cf8a88a4ab601e6a29ef1f1b07'
assert hashlib.sha256((base/'questions_blind.jsonl').read_bytes()).hexdigest()==sha
qs=[json.loads(s) for s in (base/'questions_blind.jsonl').read_text().splitlines()]
rs=[json.loads(s) for s in (root/'results.jsonl').read_text().splitlines()]
old=[json.loads(s) for s in (base/'results_rerun/adjudicated_strict.jsonl').read_text().splitlines()]
assert len(qs)==len(rs)==len(old)==30
assert {x['id'] for x in qs}=={x['id'] for x in rs}=={x['id'] for x in old}
R={x['id']:x for x in rs}; O={x['id']:x for x in old}
def norm(s): return s.casefold().replace('/','\\').replace('（只在台式机能打开）','').strip()
rows=[]
for q in qs:
 r=R[q['id']]; prev=O[q['id']]
 assert r['question']==q['question'] and r['question_sha256']==sha
 paths={norm(q['windows_path']),*(norm(a['windows']) for a in q['aliases'])}
 details=[]
 for h in r['hits']:
  if h['rank']>5: continue
  b=h['block']; m=re.search(r'(Desktop 条目|Zotero 条目|EndNote 条目)\s+(\S+)',b); key=m.group(2) if m else ''
  same=key.casefold().startswith('dsk-'+q['sha256'][:16]) or norm(h['source_pdf']) in paths or ('同一作品另有' in b[:650] and ('dsk-'+q['sha256'][:16]) in b[:650].casefold())
  alias=[]
  if same:
   # The explicit alias list maps a different PDF's physical page. Never transfer a page from another edition without this mapping.
   alias=[(a,int(p)) for a,p in re.findall(r'(DSK-[0-9a-f]{16})（PDF 第\s*(\d+)\s*页(?:，同页文字)?）',b,re.I)]
  mapped=[p for a,p in alias if a.casefold()=='dsk-'+q['sha256'][:16] and '同页文字' in b.split(a+'（PDF 第 '+str(p)+' 页',1)[-1][:25]]
  page_ok=same and (abs(h['pdf_page']-q['pdf_page'])<=1 and (key.casefold().startswith('dsk-'+q['sha256'][:16]) or norm(h['source_pdf']) in paths) or any(abs(p-q['pdf_page'])<=1 for p in mapped))
  details.append(dict(rank=h['rank'],key=key,page=h['pdf_page'],same_work=same,page_hit=page_ok,alias_pages=alias,target_alias_pages=mapped,candidate_title='题目候选' in h['heading'],garbled_title=bool(re.search(r'^\s*[1-5]\.\s*<[0-9a-fA-F]{16,}>',h['heading'])),desktop_only='只在台式机能打开' in h['source_pdf'],table_hint='疑似表格' in h['heading']))
 matching=[d for d in details if d['same_work']]
 work=bool(matching); page=any(d['page_hit'] for d in matching)
 raw=r['raw_output']
 row=dict(id=q['id'],group=q['group'],work_hit=work,page_hit=page,old_work_hit=prev['work_hit'],old_page_hit=prev['page_hit'],page_change='变好' if page and not prev['page_hit'] else '变差' if not page and prev['page_hit'] else '不变',work_change='变好' if work and not prev['work_hit'] else '变差' if not work and prev['work_hit'] else '不变',expected_pdf_page=q['pdf_page'],matching=matching,hits=details,translated='中文问题已译成英文检索' in raw,untranslated='未翻译' in raw,internal_60s=bool(re.search(r'60\s*秒|内部截止',raw)),desktop_incomplete=bool(re.search(r'台式机来源.{0,15}(?:没跑完|未跑完|未完成)',raw)),exit_code=r['exit_code'],elapsed_s=r['elapsed_s'])
 rows.append(row)
(root/'adjudicated_strict_mapped.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows))
(root/'comparison_strict_mapped.jsonl').write_text(''.join(json.dumps({k:x[k] for k in ('id','group','work_hit','page_hit','old_work_hit','old_page_hit','work_change','page_change','internal_60s','desktop_incomplete')},ensure_ascii=False)+'\n' for x in rows))
for group in ('book','literature','chinese','ocr','ALL'):
 a=[x for x in rows if x['group']==group or group=='ALL']
 print(group,len(a),'work',sum(x['work_hit'] for x in a),'page',sum(x['page_hit'] for x in a),'old_work',sum(x['old_work_hit'] for x in a),'old_page',sum(x['old_page_hit'] for x in a))
print('page change',collections.Counter(x['page_change'] for x in rows))
print('work change',collections.Counter(x['work_change'] for x in rows))
print('flags', {k:sum(bool(x[k]) for x in rows) for k in ('translated','untranslated','internal_60s','desktop_incomplete')})
for x in rows:
 print(x['id'],x['group'],'old',int(x['old_work_hit']),int(x['old_page_hit']),'new',int(x['work_hit']),int(x['page_hit']),x['page_change'],'matching',[(d['rank'],d['page'],d['key'],d['alias_pages']) for d in x['matching']])
