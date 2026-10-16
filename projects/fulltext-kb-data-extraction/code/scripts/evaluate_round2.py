#!/usr/bin/env python3
"""Frozen retrieval evaluation; full raw top5 and rc-kb stdout saved, no data uploaded."""
import csv,hashlib,json,re,sqlite3,subprocess,sys,time
from pathlib import Path
import numpy as np
from fastembed import TextEmbedding
sys.path.insert(0,str(Path(__file__).parent))
from ftkb import search as bm25
from bilingual import search as bilingual
R=Path(__file__).resolve().parent.parent
sets=[('round2',R/'questions_round2.jsonl'),('homepage_en',R/'questions_en.jsonl')]
translated={
 'R12':'During hurricane intensification, within roughly how many kilometers of the storm center can low equivalent-potential-temperature inflow undercut rotational air?',
 'R13':'What was the orbital altitude in kilometers of the QuikSCAT polar orbit satellite?',
 'R14':'At which five elevations were wind sensors deployed for the Masdar City urban canopy validation?',
 'R15':'How many discrete levels were used for the building model in the semi-active tuned liquid column damper study?',
 'R16':'What radius of maximum winds in kilometers was chosen as a typhoon parameter in the analytical wind field comparison of three typhoons?'
}

def canon(s):return re.sub(r'[^a-z0-9\u3400-\u9fff]','',s.casefold())
def dedup(results,n=5):
 seen=set();out=[]
 for x in results:
  ident=(canon(x['title']),x['page'])
  if ident in seen:continue
  seen.add(ident);out.append(x)
  if len(out)>=n:break
 return out

def rerank(query,lex,model):
 # For bilingual cases: query-only translated candidate generation; semantic scoring uses original Chinese.
 if not lex:return []
 texts=[x['title']+' '+x['text'][:1200] for x in lex]
 emb=np.asarray(list(model.embed(texts,batch_size=24)))
 qv=np.asarray(list(model.query_embed(query))[0]);order=np.argsort(emb@qv)[::-1]
 semrank={int(i):r for r,i in enumerate(order,1)}
 scored=[(1/(60+i)+1/(60+semrank[i-1]),x) for i,x in enumerate(lex,1)]
 return [x for _,x in sorted(scored,key=lambda v:-v[0])]

def title_match(x,q):
 # exact normalized title alias across Zotero/EndNote; key match remains recorded separately
 return x['key']==q['answer_key'] or canon(x['title'])==canon(q['answer_title'])

def kb_search(q):
 try:
  p=subprocess.run(['rc-kb','--ctx',sys.argv[1],'search',q['question'],'-n','5'],capture_output=True,text=True,timeout=25)
  return {'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
 except Exception as e:return {'exit':-1,'stdout':'','stderr':str(e)}

def main():
 assert len(sys.argv)>1,'Pass --ctx token as single argument'
 model=TextEmbedding(model_name='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',cache_dir='./ftkb/models',threads=4)
 enmodel=TextEmbedding(model_name='BAAI/bge-small-en-v1.5',cache_dir='./ftkb/models',threads=4)
 rows=[];raw=[]
 for group,path in sets:
  sha=hashlib.sha256(path.read_bytes()).hexdigest()
  for q in (json.loads(x) for x in path.open()):
   ident=q['id'];text=q['question'];a=bm25(text,120);b=bilingual(text,120)
   variants={'bm25':a,'bilingual':b}
   if group=='homepage_en':variants['bge_en_rerank']=rerank(text,a[:60],enmodel)
   else:
    variants['multi_rerank']=rerank(text,b[:100],model)
    if ident in translated:
     # Only the translated question enters an English-language lexical search. Source pages stay local.
     et=translated[ident];pool=bm25(et,120)
     variants['query_translation_bm25']=pool
     variants['translation_multi_rerank']=rerank(text,pool[:100],model)
   kb=kb_search(q) if group=='round2' else None
   if kb:
    # Only genuine literature-card hits with key in path count; no PDF physical page inferred.
    paths=re.findall(r'^\s+([^\s]+\.md):\d+',kb['stdout'],flags=re.M)
    kb_hit=any(q['answer_key'].upper() in p.upper() and ('wiki/' in p) for p in paths)
    rows.append(dict(group=group,id=ident,stratum=q.get('stratum','homepage'),method='rc-kb',N=1,page_hit5='',doc_hit5=int(kb_hit),key_hit5=int(kb_hit),sha256=sha))
    raw.append(dict(group=group,id=ident,method='rc-kb',kb=kb,card_paths=paths))
   for method,pool in variants.items():
    top=dedup(pool,5)
    page=any(title_match(x,q) and abs(x['page']-q['answer_page'])<=1 for x in top)
    doc=any(title_match(x,q) for x in top)
    key=any(x['key']==q['answer_key'] for x in top)
    rows.append(dict(group=group,id=ident,stratum=q.get('stratum','homepage'),method=method,N=1,page_hit5=int(page),doc_hit5=int(doc),key_hit5=int(key),sha256=sha))
    raw.append(dict(group=group,id=ident,method=method,top5=[dict(key=x['key'],page=x['page'],title=x['title'],pdf=x['pdf']) for x in top]))
   print(group,ident,'BM',next(r['page_hit5'] for r in rows[::-1] if r['id']==ident and r['method']=='bm25'),'KB',kb['exit'] if kb else 'n/a',flush=True)
 fields=list(rows[0]);
 with (R/'retrieval_round2_rows.csv').open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 with (R/'retrieval_round2_raw.jsonl').open('x') as f:
  for x in raw:f.write(json.dumps(x,ensure_ascii=False)+'\n')
 groups=sorted({(x['group'],x['stratum'],x['method']) for x in rows})
 with (R/'retrieval_round2_metrics.csv').open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['group','stratum','method','N','page_hits5','doc_hits5','key_hits5']);w.writeheader()
  for group,stratum,method in groups:
   z=[x for x in rows if (x['group'],x['stratum'],x['method'])==(group,stratum,method)]
   w.writerow(dict(group=group,stratum=stratum,method=method,N=len(z),page_hits5=sum(int(x['page_hit5']) for x in z if x['page_hit5']!=''),doc_hits5=sum(x['doc_hit5'] for x in z),key_hits5=sum(x['key_hit5'] for x in z)))
 print('SAVED',len(rows),len(raw),flush=True)
if __name__=='__main__':main()
