import sqlite3,json,gzip,pathlib,random,statistics,re,hashlib,csv
R=pathlib.Path('./ftkb_desktop'); B=pathlib.Path(__file__).parent.parent
old=sqlite3.connect('file:'+str(R/'page_text.sqlite')+'?mode=ro',uri=True)
new=sqlite3.connect('file:'+str(R/'page_text_v2.sqlite')+'?mode=ro',uri=True)
assert new.execute('pragma integrity_check').fetchone()[0]=='ok'
assert new.execute('select count(*) from pages where origin="OCR 文本"').fetchone()[0]==24615
old_ocr=old.execute('select sha256,physical_page,chars,has_text,text from pages where origin="OCR 文本" order by sha256,physical_page')
new_ocr=new.execute('select sha256,physical_page,chars,has_text,text from pages where origin="OCR 文本" order by sha256,physical_page')
assert all(a==b for a,b in zip(old_ocr,new_ocr))
assert old.execute('select count(*) from pages where origin="OCR 文本"').fetchone()[0]==24615
alias={sha:json.loads(a) for sha,a in new.execute('select sha256,aliases_json from documents')}
manifest=R/'page_manifest_v2.jsonl.gz'
with gzip.open(manifest,'wt',encoding='utf8',compresslevel=6) as f:
 for sha,p,chars,has_text,origin,extractor in new.execute('select sha256,physical_page,chars,has_text,origin,extractor from pages order by sha256,physical_page'):
  f.write(json.dumps(dict(sha256=sha,physical_page=p,characters=chars,has_text=bool(has_text),origin=origin,extractor=extractor,sqlite_row=dict(table='pages',sha256=sha,physical_page=p),aliases_ref=sha,aliases=alias[sha],db_path=str(R/'page_text_v2.sqlite')),ensure_ascii=False,separators=(',',':'))+'\n')
# Explicitly bound the dual-column test to older pages with two long horizontal fields; not a universal quality metric.
candidates=[]
for sha,p,t in old.execute('select sha256,physical_page,text from pages where physical_page between 2 and 35 and origin="text_layer" and has_text=1'):
 paths=alias[sha];path=paths[0].get('wsl','')
 if '/Literature/Categorized/' not in path or len(t or '')<1200:continue
 lines=(t or '').splitlines()
 score=sum(bool(re.search(r'\S.{15,}?\s{8,}\S.{15,}',line)) for line in lines)
 if score>=3:candidates.append((sha,p,score))
random.Random(20261015).shuffle(candidates)
selected=candidates[:50]
qa=[]
for sha,p,score in selected:
 ot=old.execute('select text from pages where sha256=? and physical_page=?',(sha,p)).fetchone()[0] or ''
 nr=new.execute('select text from pages where sha256=? and physical_page=?',(sha,p)).fetchone()
 nt=(nr[0] or '') if nr else ''
 # Isolate old two-column interleaving: line with long whitespace split into left/right;
 # examine contiguous left fragments and their relative order in the new page.
 pairs=[]
 for line in ot.splitlines():
  m=re.match(r'^(.{15,}?)\s{8,}(.{15,})$',line)
  if m:
   left,right=[re.sub(r'\s+',' ',s).strip() for s in m.groups()]
   if len(left)>20 and len(right)>20:pairs.append((left,right))
 p0=pairs[0] if pairs else ('','')
 qa.append(dict(sha256=sha,page=p,path=alias[sha][0]['wsl'],column_lines=score,old_chars=len(ot),new_chars=len(nt),old_interleaved=' | '.join(p0),new_excerpt=re.sub(r'\s+',' ',nt)[:300],left_in_new=bool(p0[0] and p0[0][:35] in re.sub(r'\s+',' ',nt)),new_present=bool(nr)))
with (B/'dual_column_50.csv').open('w',newline='',encoding='utf8') as f:
 w=csv.DictWriter(f,fieldnames=qa[0].keys());w.writeheader();w.writerows(qa)
random_rows=random.Random(8192).sample(list(new.execute('select sha256,physical_page,chars from pages where origin="text_layer" and has_text=1')),30)
diffs=[]
for sha,p,nchars in random_rows:
 oldrow=old.execute('select chars from pages where sha256=? and physical_page=?',(sha,p)).fetchone()
 diffs.append(dict(sha256=sha,page=p,old_chars=oldrow[0] if oldrow else '',new_chars=nchars,difference=nchars-oldrow[0] if oldrow else ''))
with (B/'chars_diff_30.csv').open('w',newline='',encoding='utf8') as f:
 w=csv.DictWriter(f,fieldnames=diffs[0].keys());w.writeheader();w.writerows(diffs)
print(json.dumps(dict(manifest=str(manifest),manifest_bytes=manifest.stat().st_size,pages=new.execute('select origin,count(*) from pages group by origin').fetchall(),dual_candidates=len(candidates),dual_checked=len(qa),left_anchor_in_new=sum(q['left_in_new'] for q in qa),char_diff_min=min(x['difference'] for x in diffs),char_diff_median=statistics.median(x['difference'] for x in diffs),char_diff_max=max(x['difference'] for x in diffs)),ensure_ascii=False))
