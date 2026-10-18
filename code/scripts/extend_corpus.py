#!/usr/bin/env python3
"""Read-only source enumeration, incremental page indexing and inventory; WSL index only."""
import csv,json,re,sqlite3,subprocess,sys,time,unicodedata,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).parent))
from ftkb import DB,ZDB,STORAGE,init,extract
ROOT=Path('./22_Lab/06_Logs/fulltext_kb')
END=Path('./Downloads/Endnote/Phd/Phd.Data/PDF')

def norm(s):
 s=unicodedata.normalize('NFKC',s).casefold()
 s=re.sub(r'\([^)]{0,25}(?:edition|ed\.|版)[^)]*\)','',s,flags=re.I)
 return ''.join(x for x in s if x.isalnum())
def zitems():
 c=sqlite3.connect(f'file:{ZDB}?mode=ro',uri=True)
 q='''SELECT ai.key,pi.key,COALESCE(t.value,''),COALESCE(d.value,''),a.path,ty.typeName,COALESCE(doi.value,'')
 FROM itemAttachments a JOIN items ai ON ai.itemID=a.itemID
 LEFT JOIN items pi ON pi.itemID=a.parentItemID LEFT JOIN itemTypes ty ON ty.itemTypeID=pi.itemTypeID
 LEFT JOIN itemData it ON it.itemID=a.parentItemID AND it.fieldID=1 LEFT JOIN itemDataValues t ON t.valueID=it.valueID
 LEFT JOIN itemData idate ON idate.itemID=a.parentItemID AND idate.fieldID=6 LEFT JOIN itemDataValues d ON d.valueID=idate.valueID
 LEFT JOIN itemData idoi ON idoi.itemID=a.parentItemID AND idoi.fieldID=59 LEFT JOIN itemDataValues doi ON doi.valueID=idoi.valueID
 WHERE a.contentType='application/pdf' '''
 for ak,pk,title,year,path,typ,doi in c.execute(q):
  if not path or not path.startswith('storage:'):continue
  p=STORAGE/ak/path[8:]
  if not p.is_file():
   matches=list((STORAGE/ak).glob('*.pdf')) if (STORAGE/ak).exists() else []
   if len(matches)!=1:continue
   p=matches[0]
  yield dict(source='Zotero',attachment=ak,key=pk or ak,title=title or p.stem,year=(re.search(r'\d{4}',year).group() if re.search(r'\d{4}',year) else ''),type=typ or 'unknown',doi=doi.strip().lower().replace('https://doi.org/',''),pdf=str(p),size=p.stat().st_size)
def eitems():
 for p in sorted(END.rglob('*')):
  if p.suffix.lower()!='.pdf':continue
  raw=p.stem
  m=re.match(r'^.+?\s+-\s+(\d{4})\s+-\s+(.+)$',raw)
  title=m.group(2) if m else raw
  year=m.group(1) if m else ''
  low=raw.lower()
  typ='thesis' if re.search(r'\b(thesis|dissertation|博士论文|硕士论文)\b',low) else ('book' if re.search(r'\b(handbook|textbook|monograph|encyclopedia|introduction to|principles of|fundamentals of|mechanics of|theory of|2nd ed|3rd ed|4th ed|editions?)\b|教材|手册|引论|学$',low) else 'unclassified')
  aid='END-'+hashlib.sha1(str(p.relative_to(END)).encode()).hexdigest()[:16]
  yield dict(source='EndNote',attachment=aid,key=aid,title=title,year=year,type=typ,doi='',pdf=str(p),size=p.stat().st_size)
def manifest():
 all_items=list(zitems())+list(eitems())
 # DOI is reliable for Zotero; EndNote PDF filenames supply only noisy title metadata.
 seen={}
 for x in all_items:
  title=norm(x['title'])
  identity='doi:'+x['doi'] if x['doi'].startswith('10.') else ('title:'+title if len(title)>=20 else 'file:'+x['attachment'])
  # prevent within-library duplicate attachment causing inflated cross-library counts
  x['identity']=identity
  x['duplicate_of']=seen.get(identity,'')
  seen.setdefault(identity,x['attachment'])
 with (ROOT/'corpus_manifest.csv').open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(all_items[0]));w.writeheader();w.writerows(all_items)
 print('MANIFEST',len(all_items),'zotero',sum(x['source']=='Zotero' for x in all_items),'endnote',sum(x['source']=='EndNote' for x in all_items),'title_or_doi_duplicates',sum(bool(x['duplicate_of']) for x in all_items),flush=True)
 return all_items

def index(items):
 DB.parent.mkdir(parents=True,exist_ok=True)
 c=sqlite3.connect(DB);init(c)
 done={r[0] for r in c.execute('SELECT attachment FROM processed')}
 pending=[x for x in items if x['attachment'] not in done]
 print('INDEX_PENDING',len(pending),flush=True)
 def job(x):
  item=(x['attachment'],x['key'],x['title'],x['year'],x['pdf'],x['type'])
  return extract(item)
 t=time.time()
 with ThreadPoolExecutor(max_workers=8) as pool:
  for n,(item,status,pages) in enumerate(pool.map(job,pending),1):
   ak,key,title,year,pdf,typ=item;count=0
   for i,text in pages:
    cur=c.execute('INSERT OR IGNORE INTO pages(attachment,key,title,year,type,page,text,pdf) VALUES(?,?,?,?,?,?,?,?)',(ak,key,title,year,typ,i,text,pdf))
    if cur.rowcount:c.execute('INSERT INTO page_fts(rowid,title,text) VALUES(?,?,?)',(cur.lastrowid,title,text));count+=1
   if not count and status=='ok':status='no_text'
   c.execute('INSERT OR IGNORE INTO processed VALUES(?,?,?,?)',(ak,status,count,time.time()-t));c.commit()
   if n%100==0:print('INDEXED',n,'/',len(pending),'elapsed',round(time.time()-t),'pages',c.execute('select count(*) from pages').fetchone()[0],flush=True)
 print('INDEX_FINISHED',len(pending),round(time.time()-t),flush=True)

def report(items):
 c=sqlite3.connect(DB)
 st=dict(c.execute('SELECT attachment,status FROM processed'))
 data=[]
 for x in items:
  y=dict(x);y['size']=int(y['size']);y['status']=st.get(x['attachment'],'missing');data.append(y)
 for src in ('Zotero','EndNote'):
  subset=[x for x in data if x['source']==src]
  print(src,'attachments',len(subset),'unique_all',sum(not x['duplicate_of'] for x in subset),'bytes',sum(x['size'] for x in subset),'statuses', {s:sum(x['status']==s for x in subset) for s in sorted(set(x['status'] for x in subset))},'types',{t:sum(x['type']==t for x in subset) for t in sorted(set(x['type'] for x in subset))},flush=True)
 print('TOTAL unique',sum(not x['duplicate_of'] for x in data),'pages',c.execute('select count(*) from pages').fetchone()[0],flush=True)
 with (ROOT/'corpus_inventory_stats.json').open('x') as f:
  json.dump({'by_source':{s:{'attachments':sum(x['source']==s for x in data),'unique_within_and_cross':sum(x['source']==s and not x['duplicate_of'] for x in data),'bytes':sum(x['size'] for x in data if x['source']==s),'status':{k:sum(x['source']==s and x['status']==k for x in data) for k in ('ok','no_text','missing')},'types':{k:sum(x['source']==s and x['type']==k for x in data) for k in sorted({x['type'] for x in data})}} for s in ('Zotero','EndNote')},'total_unique':sum(not x['duplicate_of'] for x in data),'indexed_pages':c.execute('select count(*) from pages').fetchone()[0]},f,ensure_ascii=False,indent=2)
if __name__=='__main__':
 items=manifest() if 'build' in sys.argv else list(csv.DictReader((ROOT/'corpus_manifest.csv').open()))
 if 'build' in sys.argv or 'resume' in sys.argv:index(items)
 report(items)
