import json,subprocess,pathlib,re,hashlib,time,os
base=pathlib.Path(__file__).parent
questions=base/'questions_blind.jsonl'
expected=(base/'freeze.sha256').read_text().split()[0]
assert hashlib.sha256(questions.read_bytes()).hexdigest()==expected,'question file changed after freeze'
q=[json.loads(s) for s in questions.read_text().splitlines()]
assert len(q)==30
ctx=os.environ['RC_CTX']; dest=base/'results.jsonl'
completed={json.loads(line)['id'] for line in dest.read_text().splitlines()} if dest.exists() else set()
with dest.open('a') as f:
 for x in q:
  if x['id'] in completed: continue
  start=time.monotonic()
  try:
   p=subprocess.run(['rc-kb','--ctx',ctx,'pages',x['question'],'-n','5'],capture_output=True,text=True,timeout=90)
   raw=p.stdout; err=p.stderr; code=p.returncode
  except subprocess.TimeoutExpired as e:
   raw=(e.stdout or b'').decode(errors='replace') if isinstance(e.stdout,bytes) else (e.stdout or '')
   err='timeout';code=124
  blocks=re.split(r'(?m)^\s*(?=[1-5]\. )',raw)
  hits=[]
  for b in blocks:
   m=re.match(r'\s*([1-5])\. .*?PDF 第\s*(\d+)\s*页',b)
   if not m:continue
   k=re.search(r'(?:Zotero|EndNote) 条目\s+([^\s/；]+)',b)
   attach=re.search(r'/ 附件\s+([^\s]+)',b)
   pdf=re.search(r'(?m)^\s*PDF：([^\n]+)',b)
   hits.append({'rank':int(m[1]),'pdf_page':int(m[2]),'key':k[1] if k else '', 'attachment':attach[1] if attach else '', 'source_pdf':pdf[1].strip() if pdf else '', 'heading':b.splitlines()[0].strip()})
  norm=lambda s: re.sub(r'[^a-z0-9\u4e00-\u9fff]+','',s.lower())
  for h in hits:
   # Same physical PDF, Zotero item key, or normalized *complete* work title; OCR may have corrupt metadata.
   h['same_work']=bool(h['source_pdf']==x['source_pdf'] or h['key']==x['source_key'] or (not x['ocr'] and norm(x['title']) and norm(x['title']) in norm(h['heading'])))
   h['page_hit']=h['same_work'] and abs(h['pdf_page']-x['pdf_page'])<=1
  obj={'id':x['id'],'group':x['group'],'expected_key':x['source_key'],'expected_pdf_page':x['pdf_page'],'question':x['question'],'exit_code':code,'elapsed_s':round(time.monotonic()-start,2),'hits':hits,'work_hit':any(h['same_work'] for h in hits),'page_hit':any(h['page_hit'] for h in hits),'raw_output':raw,'stderr':err}
  f.write(json.dumps(obj,ensure_ascii=False)+'\n');f.flush()
  print(x['id'],len(hits),obj['page_hit'],obj['work_hit'],round(obj['elapsed_s'],1),flush=True)
