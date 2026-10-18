import csv, re, sqlite3, json, hashlib, difflib, collections
from pathlib import Path
ROOT=Path(__file__).parent
queue=Path('./platform/reports/ftkb_desktop_merge_queue.md').read_text()
clusters={r['work_id']:r for r in csv.DictReader(open('./22_Lab/06_Logs/fulltext_kb/desktop_inventory/metadata/work_clusters_v2.csv',encoding='utf-8-sig'))}
parts=re.findall(r'^- 实验室合并、平台未合并：实验室 WORK2-\d+.*?(?=^- 实验室合并、平台未合并：|\Z)',queue,re.M|re.S)
assert len(parts)==127,len(parts)
DBs=['./ftkb_desktop/page_text_v2.sqlite','./ftkb_desktop/djvu_pdg.sqlite','./ftkb_desktop/ocr_round2.sqlite']
cons=[sqlite3.connect('file:'+p+'?mode=ro',uri=True) for p in DBs]
def norm(s):return re.sub(r'[^\w]+','',s.casefold())
def pages(sha):
 for c in cons:
  try:
   rows=c.execute('select physical_page,text from pages where sha256=? order by physical_page limit 6',(sha,)).fetchall()
   if rows and any(t for _,t in rows):return rows
  except sqlite3.Error:pass
 return []
def samples(sha):
 rows=pages(sha);return [(p,norm(t or '')) for p,t in rows if len(norm(t or ''))>=160][:4]
records=[]
for i,g in enumerate(parts,1):
 w=re.search(r'WORK2-\d+',g).group(); ids=re.findall(r'DSK-[0-9a-f]{16}',g);c=clusters[w];shas=c['desktop_sha256'].split(' | ')
 assert len(ids)==len(shas) and all(x[4:]==s[:16] for x,s in zip(ids,shas)),(w,ids,shas)
 texts=[samples(s) for s in shas]
 # page equality requires substantial text, independent of metadata/title.  A single common page is insufficient to merge a whole work.
 fingerprints=[{hashlib.sha256(t.encode()).hexdigest():p for p,t in ss if len(t)>350} for ss in texts]
 comparisons=[]
 for a in range(len(ids)):
  for b in range(a+1,len(ids)):
   x,y=texts[a],texts[b]; common=set(fingerprints[a])&set(fingerprints[b]);
   sim=round(difflib.SequenceMatcher(None,x[0][1][:1500],y[0][1][:1500],autojunk=False).ratio(),3) if x and y else 0
   comparisons.append(dict(a=a,b=b,common=len(common),sim=sim,pa=[fingerprints[a][h] for h in common],pb=[fingerprints[b][h] for h in common]))
 rec=dict(n=i,work=w,title=c['titles'],merge_evidence=c['merge_evidence'],ids=ids,shas=shas,meta=[{'pages':[(p,len(t)) for p,t in ss], 'first':(pages(s)[0][1] or '')[:370] if pages(s) else ''} for s,ss in zip(shas,texts)],pairs=comparisons)
 records.append(rec)
with open(ROOT/'diagnostics.jsonl','w') as f:
 for r in records:f.write(json.dumps(r,ensure_ascii=False)+'\n')
for r in records:
 ps=r['pairs']; n=len(r['ids']); strong=sum(p['common']>=2 for p in ps); one=sum(p['common']==1 for p in ps); none=sum(p['common']==0 for p in ps)
 print(f"{r['n']:3} {r['work']} n={n:2} strong={strong} one={one} none={none} sim={[p['sim'] for p in ps[:5]]} {r['title'][:65]}")
 for j,m in enumerate(r['meta'][:4]):print('  ',r['ids'][j],m['pages'][:3],re.sub(r'\s+',' ',m['first'])[:130])
