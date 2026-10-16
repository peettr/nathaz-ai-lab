import concurrent.futures, json, pathlib, sqlite3, time
import fitz
root=pathlib.Path.home()/'ftkb_text'
con=sqlite3.connect(root/'page_text_v2.sqlite')
items=[(s,json.loads(a)[0]['wsl']) for s,a in con.execute('select sha256,aliases_json from documents order by sha256')]
def inspect(item):
 sha,path=item
 try:
  doc=fitz.open(path)
  meta=doc.metadata or {}; n=len(doc); lines=[]; largest=[]
  if n:
   p=doc[0]
   blocks=p.get_text('dict')['blocks']
   candidates=[]
   for b in blocks:
    if b.get('type')!=0:continue
    for line in b.get('lines',[]):
     text=''.join(span.get('text','') for span in line.get('spans',[])).strip()
     if text:
      lines.append(text)
      candidates.append((max((s.get('size',0) for s in line.get('spans',[])),default=0),text))
   largest=[{'size':round(size,2),'text':text} for size,text in sorted(candidates,reverse=True)[:8]]
  doc.close()
  return {'sha256':sha,'path':path,'metadata':meta,'pages':n,'first_lines':lines[:15],'largest_lines':largest,'error':''}
 except Exception as e:return {'sha256':sha,'path':path,'metadata':{},'pages':0,'first_lines':[],'largest_lines':[],'error':str(e)}
start=time.monotonic()
existing=set()
if (root/'pdf_meta.jsonl').exists():
 with open(root/'pdf_meta.jsonl') as inp:
  for line in inp:
   try:existing.add(json.loads(line)['sha256'])
   except json.JSONDecodeError:break
todo=[x for x in items if x[0] not in existing]
print('RESUME',len(existing),len(todo),flush=True)
with open(root/'pdf_meta.jsonl','a') as out,concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
 for i,row in enumerate(pool.map(inspect,todo,chunksize=1),1):
  out.write(json.dumps(row,ensure_ascii=False)+'\n')
  if i%200==0:
   out.flush();print('META',len(existing)+i,len(items),round(time.monotonic()-start),flush=True)
print('META_FINAL',len(existing)+len(todo),round(time.monotonic()-start),flush=True)
