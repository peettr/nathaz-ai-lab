import os,re,json,csv,zipfile,sqlite3,collections,unicodedata,glob,hashlib,random,time
from pathlib import Path
B=Path(__file__).parent; ROOT=B.parent
END=Path('./Downloads/Endnote/Phd/Phd.Data/PDF')
DOI=re.compile(r'\b10\.\d{4,9}/[^\s\x00-\x1f<>"{}]+',re.I)
YEAR=re.compile(r'\b(?:18|19|20)\d{2}\b')
ISBN=re.compile(r'\b(?:97[89][-\d ]{10,17}|\d[-\d ]{8,15}[\dXx])\b')
def norm(s):
 s=unicodedata.normalize('NFKC',s or '').casefold();return re.sub(r'[^\w\u3400-\u9fff]+','',s)
def doi(s):
 m=DOI.search(s or '');return m.group().rstrip('.,;)').lower() if m else ''
def textnorm(s):return re.sub(r'\W+','',unicodedata.normalize('NFKC',s or '').casefold())
def writecsv(name,rows,fields):
 with open(B/name,'w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
def y(s):
 m=YEAR.search(str(s or ''));return m.group() if m else ''
# EndNote MYD variable records: parse length-coded author/year/title; never mistake text bytes for a database record without checking lengths.
with zipfile.ZipFile('./Downloads/Endnote/Phd/Phd.enl') as z: raw=z.read('refs.MYD')
pat=re.compile(rb'([\x08-\xff])\x00\x00([^\x00]{5,250}?)\x04\x00\x00((?:18|19|20)\d\d)([\x08-\xff])\x00\x00([^\x00]{8,400})')
hits=[]
for m in pat.finditer(raw):
 al=m.group(1)[0];tl=m.group(4)[0];auth=m.group(2)
 if len(auth)!=al or tl<8:continue
 title=raw[m.start(5):m.start(5)+tl]
 if b'\x00' in title or len(title)!=tl:continue
 hits.append((m.start(),auth.decode('utf8','replace'),m.group(3).decode(),title.decode('utf8','replace')))
# Restrict each record to next verified record; uncertain fields are not inferred.
allpdf=[p for p in END.glob('*/*') if p.suffix.lower()=='.pdf']
byname=collections.defaultdict(list)
for p in allpdf:byname[norm(p.name)].append(str(p))
idx=sqlite3.connect('file:./ftkb/index.sqlite?mode=ro',uri=True)
indexpaths={os.path.normpath(p): (key,attachment,title,year,typ) for p,key,attachment,title,year,typ in idx.execute('select pdf,key,attachment,title,year,type from pages where page=1 and pdf is not null')}
local_first=collections.defaultdict(dict)
for p,n,t in idx.execute('select pdf,page,text from pages where page in (1,2) and pdf is not null'):
 local_first[os.path.normpath(p)][n]=t or ''
local_fingerprints={}
for p,pp in local_first.items():
 s=textnorm((pp.get(1,'')[:14000])+(pp.get(2,'')[:14000]))
 if len(s)>=500:local_fingerprints[p]=hashlib.sha256(s.encode()).hexdigest()
endrows=[]; matched=set()
for j,(pos,author,year,title) in enumerate(hits):
 block=raw[pos:hits[j+1][0] if j+1<len(hits) else len(raw)]
 # An unparsed intervening ENL record can lie between two verified year/title records.
 # Only the first PDF reference is safely attributable to this record.
 refs=re.findall(rb'internal-pdf://([^/\x00\r\n]+)/([^\x00\r\n]+?\.pdf)',block,re.I)[:1]
 paths=[]; keys=[]
 for ident,fn in refs:
  fn=fn.decode('utf8','replace');found=[p for p in byname[norm(fn)] if Path(p).parent.name==ident.decode('ascii','replace')]
  if not found:found=byname[norm(fn)]
  if norm(title)[:12] not in norm(fn) and norm(fn)[:12] not in norm(title):found=[]
  for p in found:
   paths.append(p);matched.add(p)
   if os.path.normpath(p) in indexpaths:keys.append(indexpaths[os.path.normpath(p)][0])
 # Journal is first plausible length-coded field immediately after title, filtering pages/volume/keywords.
 tail=block[block.find(title.encode('utf8','replace'))+len(title.encode('utf8','replace')):]
 fields=[]
 for m in re.finditer(rb'([\x02-\xff])\x00\x00([^\x00]{2,150})',tail[:600]):
  if len(m.group(2))==m.group(1)[0]:fields.append(m.group(2).decode('utf8','replace'))
 journal=next((x for x in fields if ('journal' in x.lower() or 'proceedings' in x.lower() or 'wind engineering' in x.lower()) and x!=title),'')
 # Read the MYD length-coded DOI field, not a free-form regex that consumes the
 # next field marker or truncates older journal DOIs containing angle brackets.
 before=block.split(b'internal-pdf://',1)[0]
 dm=''
 for match in re.finditer(rb'([\x0c-\xff])\x00\x00((?:https?://(?:dx\.)?doi\.org/)?10\.)',before,re.I):
  length=match.group(1)[0];value=before[match.start(2):match.start(2)+length]
  if len(value)!=length or any(c<32 for c in value):continue
  candidate=re.sub(r'^https?://(?:dx\.)?doi\.org/','',value.decode('utf8','replace'),flags=re.I).lower()
  if candidate.startswith('10.') and '/' in candidate and len(candidate)>=16:dm=candidate;break
 endrows.append(dict(record_id=f'ENL-{j+1:05d}',title=title,authors=author.replace('\r','; '),year=year,journal=journal,doi=dm,item_type='',attachment_names=' | '.join(fn.decode('utf8','replace') for _,fn in refs),pdf_paths=' | '.join(sorted(set(paths))),end_keys=' | '.join(sorted(set(keys))),metadata_confidence='parsed_author_year_title; journal/type incomplete'))
# Attachments with no verified parsed record remain explicitly unlinked.
for p in allpdf:
 if str(p) not in matched:
  i=indexpaths.get(os.path.normpath(str(p)))
  endrows.append(dict(record_id='UNLINKED-'+hashlib.sha256(str(p).encode()).hexdigest()[:12],title=i[2] if i else '',authors='',year=i[3] if i else '',journal='',doi='',item_type=i[4] if i else '',attachment_names=p.name,pdf_paths=str(p),end_keys=('END-'+i[0]) if i else '',metadata_confidence='attachment_unlinked_to_ENL'))
writecsv('endnote_records.csv',endrows,['record_id','title','authors','year','journal','doi','item_type','attachment_names','pdf_paths','end_keys','metadata_confidence'])
# Desktop documents are defined by the completed stage-1 SQLite; no remote SSH required for first-page text.
db=sqlite3.connect('file:./ftkb_desktop/page_text.sqlite?mode=ro',uri=True)
remote=[]; fingerprints={};pagecounts={}
for sha,aliases in db.execute('select sha256,aliases_json from documents'):
 aa=json.loads(aliases);paths=[a['wsl'] for a in aa];path=paths[0]; page= db.execute('select text from pages where sha256=? and physical_page=1',(sha,)).fetchone(); page2=db.execute('select text from pages where sha256=? and physical_page=2',(sha,)).fetchone()
 first=((page or [''])[0] or '')[:14000]; second=((page2 or [''])[0] or '')[:14000]
 if len(textnorm(first+second))>=500:fingerprints['D:'+sha]=hashlib.sha256(textnorm(first+second).encode()).hexdigest()
 n=db.execute('select count(*) from pages where sha256=?',(sha,)).fetchone()[0];pagecounts[sha]=n
 # PDF embedded title/author is inaccessible while the approved desktop ControlMaster is unavailable; use filename and OCR text only.
 stem=Path(path).stem; candidate=re.sub(r'^(?:[A-Za-z\u4e00-\u9fff .,&-]+?)\s+-\s+((?:18|19|20)\d\d)\s+-\s+','',stem)
 year=y(stem) or y(first[:1200]); candidates=[s.strip(' -\t') for s in first.splitlines()[:20] if 12<=len(s.strip())<=180 and not DOI.search(s) and not re.match(r'^(?:abstract|journal|copyright|issn|www\.)',s.strip(),re.I)]
 # Filename is safer than a random first-page line when it contains an author-year-title pattern.
 title=candidate if candidate!=stem else (candidates[0] if candidates and len(stem)<6 else stem)
 author=stem.split(' - ')[0] if candidate!=stem else ''
 ar=re.search(r'\b(?:arxiv[:. ]*)?(\d{4}\.\d{4,5})(?:v\d+)?\b',first[:9000],re.I)
 dm=doi(first[:18000]+ '\n'+second[:8000]);isb=ISBN.search(first[:5000]);
 isbn=isb.group() if isb and re.sub(r'\D','',isb.group()).__len__() in (10,13) else ''
 origin='filename_author_year_title' if candidate!=stem else ('filename' if title==stem else 'first_page_candidate')
 doi_join=dm if dm and doi(first[:1200])==dm else ''
 remote.append(dict(sha256=sha,path=path,all_paths=' | '.join(paths),windows_paths=' | '.join(a.get('windows','') for a in aa),title=title,authors=author,year=year,doi=dm,doi_join=doi_join,arxiv=ar.group(1) if ar else '',isbn=isbn,pages=n,source_field=origin+'; DOI/arxiv/ISBN:first_2_pages',confidence='medium' if origin.startswith('filename_author') else 'low',first_two_page_fingerprint=fingerprints.get('D:'+sha,'')))
writecsv('desktop_records.csv',remote,['sha256','path','all_paths','windows_paths','title','authors','year','doi','doi_join','arxiv','isbn','pages','source_field','confidence','first_two_page_fingerprint'])
# Zotero parent item metadata, only attachment-backed works.
zc=sqlite3.connect('file:./ftkb/zotero.sqlite?mode=ro',uri=True)
meta=collections.defaultdict(dict)
for item,field,value in zc.execute('select d.itemID,f.fieldName,v.value from itemData d join fieldsCombined f on d.fieldID=f.fieldID join itemDataValues v on d.valueID=v.valueID where f.fieldName in ("title","DOI","date","publicationTitle","ISBN")'):
 meta[item][field]=str(value)
cre=collections.defaultdict(list)
for item,name in zc.execute('select ic.itemID,c.lastName from itemCreators ic join creators c on ic.creatorID=c.creatorID order by ic.itemID,ic.orderIndex'):cre[item].append(name)
zrows=[]
for att,key,parent,path,typ in zc.execute('select a.itemID,i.key,a.parentItemID,a.path,t.typeName from itemAttachments a join items i on i.itemID=a.itemID join itemTypes t on t.itemTypeID=i.itemTypeID where a.contentType="application/pdf"'):
 par=parent or att;d=meta[par]; t=zc.execute('select t.typeName from items i join itemTypes t on i.itemTypeID=t.itemTypeID where i.itemID=?',(par,)).fetchone()
 zrows.append(dict(id='Z:'+key,title=d.get('title',''),authors='; '.join(cre[par]),year=y(d.get('date','')),doi=doi(d.get('DOI','')),isbn=d.get('ISBN',''),type=t[0] if t else '',pdf_path=str(Path('./Zotero/storage')/key/(path or '').replace('storage:',''))))
# EndNote records attached PDF only, unlinked attachments count as distinct provisional records.
elements=[]
for x in zrows:elements.append(dict(source='Zotero',id=x['id'],title=x['title'],year=x['year'],doi=x['doi'],path=x['pdf_path'],sha='',type=x['type']))
for x in endrows:
 if not x['pdf_paths']:continue
 for p in x['pdf_paths'].split(' | '):elements.append(dict(source='EndNote',id='E:'+x['record_id']+':'+hashlib.sha1(p.encode()).hexdigest()[:8],end_key=x['end_keys'],title=x['title'],year=x['year'],doi=x['doi'],path=p,sha='',type=x['item_type']))
for x in remote:elements.append(dict(source='Desktop',id='D:'+x['sha256'],title=x['title'],year=x['year'],doi=x['doi_join'],path=x['path'],sha=x['sha256'],type='',confidence=x['confidence']))
N=len(elements);parent=list(range(N));reasons=collections.defaultdict(set)
def root(i):
 while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
 return i
def merge(i,j,reason):
 a,b=root(i),root(j)
 if a!=b:parent[b]=a
 reasons[tuple(sorted((i,j)))].add(reason)
# Conservative non-transitive candidate key: title exact after punctuation removal + year difference <=1, length >= 24.
bydoi={};bytitle=collections.defaultdict(list);byfp={}
for i,e in enumerate(elements):
 k=e['doi'];nt=norm(e['title'])
 if k:
  if k in bydoi:merge(i,bydoi[k],'DOI')
  else:bydoi[k]=i
 if len(nt)>=24 and e['year'] and (e['source']!='Desktop' or e['confidence']=='medium'):
  for j in bytitle[nt]:
   if abs(int(e['year'])-int(elements[j]['year']))<=1 and (not k or not elements[j]['doi'] or k==elements[j]['doi']):merge(i,j,'title_year')
  bytitle[nt].append(i)
 if e['source']=='Desktop' and (fp:=fingerprints.get(e['id'])):
  if fp in byfp:merge(i,byfp[fp],'first_2_pages_exact')
  else:byfp[fp]=i
 if e['source']!='Desktop' and (fp:=local_fingerprints.get(os.path.normpath(e['path']))):
  if fp in byfp:merge(i,byfp[fp],'first_2_pages_exact')
  else:byfp[fp]=i
# Explicit byte-equivalent local cross-library path match where available.
localhash=collections.defaultdict(list)
for l in open(ROOT/'local_hashes.jsonl',encoding='utf8'):
 x=json.loads(l);localhash[x['path']].append(x.get('sha256',''))
# No synthetic near-duplicate merge based on title snippets alone.
groups=collections.defaultdict(list)
for i,e in enumerate(elements):groups[root(i)].append(e)
group_reasons=collections.defaultdict(set)
for pair,rs in reasons.items():
 if root(pair[0])==root(pair[1]):group_reasons[root(pair[0])].update(rs)
rows=[];newdesktop=0
for wi,(groupid,g) in enumerate(groups.items(),1):
 sources={e['source'] for e in g};newdesktop+=('Desktop' in sources and sources=={'Desktop'})
 rr=sorted(group_reasons[groupid])
 rows.append(dict(work_id=f'WORK-{wi:06d}',sources=';'.join(sorted(sources)),zotero_keys=' | '.join(e['id'][2:] for e in g if e['source']=='Zotero'),endnote_ids=' | '.join(e['id'] for e in g if e['source']=='EndNote'),endnote_keys=' | '.join(sorted(set(k for e in g if e['source']=='EndNote' for k in e['end_key'].split(' | ') if k))),desktop_sha256=' | '.join(e['sha'] for e in g if e['source']=='Desktop'),titles=' | '.join(sorted(set(e['title'] for e in g if e['title']))[:4]),doi=' | '.join(sorted(set(e['doi'] for e in g if e['doi']))),merge_evidence=';'.join(rr) if len(g)>1 else 'singleton',member_count=len(g)))
writecsv('work_clusters.csv',rows,['work_id','sources','zotero_keys','endnote_ids','endnote_keys','desktop_sha256','titles','doi','merge_evidence','member_count'])
books=[]
for e in remote:
 if e['path'].startswith('./Book/') or (e['pages']>=150 and (e['isbn'] or re.search('book|教材|handbook|monograph',e['path'],re.I))):
  # Scanned = first two pages both empty (only a clue, not a full-document proof).
  p1=db.execute('select has_text from pages where sha256=? and physical_page in (1,2)',(e['sha256'],)).fetchall()
  books.append(dict(title=e['title'],authors=e['authors'],year=e['year'],isbn=e['isbn'],source='Desktop',id=e['sha256'],pages=e['pages'],scanned='suspected' if p1 and not any(v[0] for v in p1) else 'unknown/mixed',confidence=e['confidence']))
for e in zrows:
 if e['type'] in ('book','bookSection','thesis'):books.append(dict(title=e['title'],authors=e['authors'],year=e['year'],isbn=e['isbn'],source='Zotero',id=e['id'],pages='',scanned='unknown',confidence='catalog'))
for e in endrows:
 if e['pdf_paths'] and (e['item_type']=='book' or re.search(r'\b(book|handbook|turbulence modeling for cfd)\b',e['title'],re.I)):
  books.append(dict(title=e['title'],authors=e['authors'],year=e['year'],isbn='',source='EndNote',id=e['record_id'],pages='',scanned='unknown',confidence=e['metadata_confidence']))
writecsv('books.csv',books,['title','authors','year','isbn','source','id','pages','scanned','confidence'])
summary=dict(endnote_parsed_records=len(hits),endnote_pdf_attachments=len(allpdf),endnote_unlinked_attachments=len(allpdf)-len(matched),desktop_docs=len(remote),zotero_pdf_attachments=len(zrows),total_members=N,work_clusters=len(rows),desktop_only_clusters=newdesktop,books_candidates=len(books),desktop_doi=sum(bool(e['doi']) for e in remote),desktop_doi_join=sum(bool(e['doi_join']) for e in remote),desktop_title_low=sum(e['confidence']=='low' for e in remote))
(B/'counts.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(summary)
