import csv,json,re,unicodedata,sqlite3,collections,hashlib,random,pathlib,statistics
B=pathlib.Path(__file__).parent;R=pathlib.Path('./ftkb_desktop'); DB=sqlite3.connect('file:'+str(R/'page_text_v2.sqlite')+'?mode=ro',uri=True)
def load(name):
 with (B/name).open(newline='',encoding='utf8') as f:return list(csv.DictReader(f))
def norm(s):return re.sub(r'[^\w\u3400-\u9fff]','',unicodedata.normalize('NFKC',s or '').casefold())
def clean(s):return re.sub(r'\W+','',unicodedata.normalize('NFKC',s or '').casefold())
def doi(s):
 s=(s or '').strip().lower().rstrip('.,;)');return s if s.isascii() and re.fullmatch(r'10\.\d{4,9}/[^\s<>"{}]+',s) else ''
def write(name,rows,fields):
 with (B/name).open('w',encoding='utf8',newline='') as f:
  w=csv.DictWriter(f,fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
meta={}
for line in (R/'pdf_meta.jsonl').open(encoding='utf8'):
 try:r=json.loads(line);meta[r['sha256']]=r
 except:pass
D=load('desktop_records_v2.csv');E=load('endnote_records_v2.csv');ad=load('doi_verified_adjudicated.csv')
verified={(r['source'],r['source_id']):r for r in ad if r['adjudicated_judgement']=='一致' and r['adjudicated_exists']=='yes'}
def textfp(s):
 s=clean(s[:14000]);return hashlib.sha256(s.encode()).hexdigest() if len(s)>=500 else ''
# The metadata PDF title field is often Acrobat's generic title; compare to a plausible largest-font line.
for r in D:
 m=meta.get(r['sha256'],{}); info=m.get('metadata') or {};inf=(info.get('title') or '').strip();aut=(info.get('author') or '').strip()
 large=[x.get('text','').strip() for x in m.get('largest_lines',[]) if 12<=len(x.get('text','').strip())<=220]
 large=next((x for x in large if not re.search(r'^(abstract|journal|vol\.|\d{4}$|untitled|microsoft word|adobe)',x,re.I)), '')
 inf='' if re.search(r'^(untitled|microsoft word|adobe|scan|document|\d+|booktext@|PII:|Title of paper$|SSReader|PowerPoint Presentation|Form_|.*\.book$)',inf,re.I) or len(inf)<12 or (inf.lower().startswith('doi:')) else inf
 candidate=inf or large
 agreement=bool(inf and large and (norm(inf)==norm(large) or (len(norm(inf))>16 and (norm(inf) in norm(large) or norm(large) in norm(inf)))))
 if r['title_source']=='crossref':r['confidence']='high_crossref'
 elif inf and agreement:
  r['title']=inf;r['authors']=aut or r['authors'];r['confidence']='high_pdfinfo_home';r['title_source']='pdfinfo_home'
 elif inf:
  r['title']=inf;r['authors']=aut or r['authors'];r['confidence']='medium_pdfinfo';r['title_source']='pdfinfo'
 elif large:
  r['title']=large;r['authors']=aut or r['authors'];r['confidence']='low_home';r['title_source']='home_large'
 else:r['confidence']='low_filename';r['title_source']='filename'
 r['pdfinfo_title']=inf;r['pdfinfo_author']=aut;r['home_large_line']=large;r['pdf_meta_error']=m.get('error','missing')
 r['doi_fixed_from']=''
 # Only replace a corrupted DOI if an actual ASCII DOI can be retrieved from this document's PDF Info or first-page large text.
 if r['doi'] and not r['doi'].isascii():
  evidence=' '.join([str(x) for x in info.values() if isinstance(x,str)]+m.get('first_lines',[])+large.splitlines())
  found=set(doi(x) for x in re.findall(r'10\.\d{4,9}/[^\s<>"{}]+',evidence,re.I));found.discard('')
  # Preserve every ASCII character in its original position; the replacement may only fill non-ASCII OCR glyphs.
  original=r['doi'].lower().strip().rstrip('.,;)')
  matching=[x for x in found if len(x)==len(original) and all((c==x[i] if c.isascii() else x[i].isalnum()) for i,c in enumerate(original)) and all(ord(c)>=33 for c in x)]
  if len(matching)==1:
   r['doi_fixed_from']=r['doi'];r['doi']=matching[0];r['doi_join']=r['doi'] if r['doi_join'] else ''
 # New engine fingerprint is not interchangeable with old engine fingerprints.
 p1=DB.execute('select text from pages where sha256=? and physical_page=1',(r['sha256'],)).fetchone()
 p2=DB.execute('select text from pages where sha256=? and physical_page=2',(r['sha256'],)).fetchone()
 r['first_two_page_fingerprint_v2']=textfp(((p1[0] or '') if p1 else '')+((p2[0] or '') if p2 else ''))
for r in E:r['doi_fixed_from']=''
# Low-confidence DOI candidates must not merge works; Crossref-consistent candidate only.
for r in D+E:
 source='desktop' if 'sha256' in r else 'endnote';key=r.get('sha256') or r['record_id']
 r['doi_verified_join']=doi(r['doi']) if (source,key) in verified else ''
write('desktop_records_v3.csv',D,list(D[0]));write('endnote_records_v3.csv',E,list(E[0]))
# Preserve requested v2 names as immutable preceding generation; v3 names denote this second-round B.
zc=sqlite3.connect('file:./ftkb/zotero.sqlite?mode=ro',uri=True)
zm=collections.defaultdict(dict)
for item,field,val in zc.execute('select d.itemID,f.fieldName,v.value from itemData d join fieldsCombined f on d.fieldID=f.fieldID join itemDataValues v on d.valueID=v.valueID where f.fieldName in ("title","DOI","date","ISBN")'):zm[item][field]=str(val)
za=[]
for key,parent,att,path in zc.execute('select i.key,a.parentItemID,a.itemID,a.path from itemAttachments a join items i on i.itemID=a.itemID where a.contentType="application/pdf"'):
 d=zm[parent or att];za.append(dict(source='Zotero',id=key,title=d.get('title',''),year=re.search(r'(?:18|19|20)\d\d',d.get('date','')).group() if re.search(r'(?:18|19|20)\d\d',d.get('date','')) else '',doi=doi(d.get('DOI','')),fp='',path='',type=''))
localfp={}
idx=sqlite3.connect('file:./ftkb/index.sqlite?mode=ro',uri=True)
for path,page,t in idx.execute('select pdf,page,text from pages where page in (1,2) and pdf is not null'):
 localfp.setdefault(path,{})[page]=t or ''
localfp={p:textfp(pp.get(1,'')+pp.get(2,'')) for p,pp in localfp.items()}
# Existing index stores Zotero/EndNote attachments; map Zotero key to the PDF path without guessing filename.
for path,key in idx.execute('select pdf,key from pages where page=1 and pdf is not null'):
 if '/Zotero/storage/' in path:
  for r in za:
   if r['id']==key:r['fp']=localfp.get(path,'');break
members=za[:]
for r in E:
 for path in filter(None,r['pdf_paths'].split(' | ')):
  members.append(dict(source='EndNote',id=r['record_id']+':'+hashlib.sha1(path.encode()).hexdigest()[:8],end_key=r['end_keys'],title=r['title'],year=r['year'],doi=r['doi_verified_join'],fp=localfp.get(path,''),path=path,type=r['item_type'],confidence=r['metadata_confidence']))
for r in D:members.append(dict(source='Desktop',id=r['sha256'],title=r['title'],year=r['year'],doi=r['doi_verified_join'],fp=r['first_two_page_fingerprint_v2'],path=r['path'],type='',confidence=r['confidence']))
parent=list(range(len(members)));why=collections.defaultdict(set)
def root(i):
 while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
 return i
def merge(i,j,reason):
 a,b=root(i),root(j)
 if a!=b:
  # Two different verified DOI are a conflict, never merge via title/fingerprint.
  aa={members[k]['doi'] for k in range(len(members)) if root(k)==a and members[k]['doi']}
  bb={members[k]['doi'] for k in range(len(members)) if root(k)==b and members[k]['doi']}
  if aa and bb and aa!=bb:return
  parent[b]=a
 why[tuple(sorted((i,j)))].add(reason)
# Avoid repeated quadratic root scans after initial DOI merge: only merge if pair DOI is compatible.
def pairmerge(i,j,reason):
 di,dj=members[i]['doi'],members[j]['doi']
 if di and dj and di!=dj:return
 a,b=root(i),root(j)
 if a!=b:parent[b]=a
 why[tuple(sorted((i,j)))].add(reason)
bydoi={};bytitle=collections.defaultdict(list);byfp={}
for i,e in enumerate(members):
 if e['doi']:
  if e['doi'] in bydoi:pairmerge(i,bydoi[e['doi']],'verified_DOI' if e['source']!='Zotero' else 'catalog_DOI')
  else:bydoi[e['doi']]=i
 nt=norm(e['title']); yr=e['year']
 if len(nt)>=24 and yr and (e['source']!='Desktop' or e.get('confidence') in ('high_crossref','high_pdfinfo_home','medium_pdfinfo')):
  for j in bytitle[nt]:
   if abs(int(yr)-int(members[j]['year']))<=1:pairmerge(i,j,'title_year')
  bytitle[nt].append(i)
 if e['fp']:
  if e['fp'] in byfp:pairmerge(i,byfp[e['fp']],'first_two_pages_exact_engine_specific')
  else:byfp[e['fp']]=i
clusters=collections.defaultdict(list)
for i,e in enumerate(members):clusters[root(i)].append((i,e))
reason=collections.defaultdict(set)
for (i,j),rs in why.items():
 if root(i)==root(j):reason[root(i)].update(rs)
rows=[]
for wi,(rt,g) in enumerate(sorted(clusters.items()),1):
 sources=set(e['source'] for _,e in g)
 rows.append(dict(work_id=f'WORK2-{wi:06d}',sources=';'.join(sorted(sources)),zotero_keys=' | '.join(e['id'] for _,e in g if e['source']=='Zotero'),endnote_ids=' | '.join(e['id'] for _,e in g if e['source']=='EndNote'),endnote_keys=' | '.join(sorted(set(k for _,e in g if e['source']=='EndNote' for k in e.get('end_key','').split(' | ') if k))),desktop_sha256=' | '.join(e['id'] for _,e in g if e['source']=='Desktop'),titles=' | '.join(sorted(set(e['title'] for _,e in g if e['title']))[:4]),doi=' | '.join(sorted(set(e['doi'] for _,e in g if e['doi']))),merge_evidence=';'.join(sorted(reason[rt])) if len(g)>1 else 'singleton',member_count=len(g)))
write('work_clusters_v2.csv',rows,list(rows[0]))
books=[]
for r in D:
 if r['path'].startswith('./Book/') or (int(r['pages'] or 0)>=150 and (r['isbn'] or re.search(r'book|教材|handbook|monograph',r['path'],re.I))):
  p=DB.execute('select has_text from pages where sha256=? and physical_page in (1,2)',(r['sha256'],)).fetchall()
  books.append(dict(title=r['title'],authors=r['authors'],year=r['year'],isbn=r['isbn'],source='Desktop',id=r['sha256'],pages=r['pages'],scanned='suspected_first_two_pages_only' if p and not any(a[0] for a in p) else 'unknown/mixed',confidence=r['confidence']))
for r in load('books.csv'):
 if r['source']!='Desktop':books.append(r)
write('books_v2.csv',books,list(books[0]))
# Different seed, three source strata; automated PDF-Info vs first-page consistency is not human verification.
rng=random.Random(20261016);audit=[]
for label,pool in [('Desktop crossref',[x for x in D if x['title_source']=='crossref']),('Desktop new PDFInfo',[x for x in D if x['title_source'] in ('pdfinfo_home','pdfinfo')]),('EndNote',[x for x in E if x['pdf_paths']])]:
 for r in rng.sample(pool,min(10,len(pool))):
  m=meta.get(r.get('sha256',''),{});ref=m.get('metadata',{}).get('title','') if m else ''
  audit.append(dict(stratum=label,id=r.get('sha256',r.get('record_id')),title=r['title'],source=r['title_source'],pdfinfo_title=ref,home_line=(m.get('largest_lines') or [{}])[0].get('text','') if m else '',title_agrees_pdfinfo=(norm(ref)==norm(r['title'])) if ref else '',manual_pdf_check='not_done'))
write('audit_round3_30.csv',audit,list(audit[0]))
print(json.dumps(dict(meta_count=len(meta),desktop=len(D),endnote_pdf_rows=sum(bool(x['pdf_paths']) for x in E),zotero=len(za),members=len(members),works=len(rows),desktop_only=sum(x['sources']=='Desktop' for x in rows),desktop_zotero_overlap=sum('Desktop' in x['sources'] and 'Zotero' in x['sources'] for x in rows),books=len(books),doi_fixed=sum(bool(x['doi_fixed_from']) for x in D+E),title_source_desktop=dict(collections.Counter(x['title_source'] for x in D)),audit=len(audit)),ensure_ascii=False))
