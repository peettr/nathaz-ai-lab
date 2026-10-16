import sqlite3,random,re,json,csv,pathlib
root=pathlib.Path('./22_Lab/06_Logs/fulltext_kb')
con=sqlite3.connect('file:./ftkb/index.sqlite?mode=ro',uri=True)
random.seed(3127)
rows=con.execute("select attachment,key,title,year,type,page,text,pdf from pages where page>=3 and length(text)>600 and length(text)<13000").fetchall()
manifest={r['attachment']:r for r in csv.DictReader(open(root/'corpus_manifest.csv'))}
books=[r for r in rows if (r[4] in ('book','bookSection') or any(w in (r[2] or '').lower() for w in ['handbook','textbook','wind engineering','atmospheric boundary layer','numerical methods','tropical cyclone','turbulence modeling'])) and r[5]>=5]
zh=[r for r in rows if len(re.findall('[\u4e00-\u9fff]',r[6]))>100 and r[4] not in ('book','bookSection')]
en=[r for r in rows if len(re.findall('[\u4e00-\u9fff]',r[6]))<10 and r[4] not in ('book','bookSection') and len(r[6])>1100]
def sample_unique(pool,n):
 random.shuffle(pool); seen=set(); out=[]
 for r in pool:
  if r[0] in seen:continue
  seen.add(r[0]);out.append(r)
  if len(out)>=n:break
 return out
out={group:sample_unique(pool,n) for group,pool,n in [('zh',zh,40),('en',en,45),('books',books,45)]}
with open(root/'blind_round3'/'discovery_pool.jsonl','w') as f:
 for group,items in out.items():
  for r in items:
   t=re.sub(r'\s+',' ',r[6]); obj={'group':group,'attachment':r[0],'key':r[1],'title':r[2],'year':r[3],'type':r[4],'page':r[5],'pdf':r[7],'excerpt':t[:1800]}; f.write(json.dumps(obj,ensure_ascii=False)+'\n')
print({k:(len(v),len(set(r[0] for r in pool))) for k,pool,v in [('zh',zh,out['zh']),('en',en,out['en']),('books',books,out['books'])]})
