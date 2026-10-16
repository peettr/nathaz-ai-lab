#!/usr/bin/env python3
"""CPU BGE-small semantic reranking over BM25 full-corpus candidates."""
import csv,hashlib,json,sys
from pathlib import Path
import numpy as np
from fastembed import TextEmbedding
sys.path.insert(0,str(Path(__file__).parent))
from ftkb import search
R=Path('./22_Lab/06_Logs/fulltext_kb')
def hybrid_search(query,n=5,model=None):
 model=model or TextEmbedding(model_name='BAAI/bge-small-en-v1.5',cache_dir='./ftkb/models',threads=4)
 b=search(query,60)
 if not b:return []
 texts=[x['title']+' '+x['text'][:1200] for x in b]
 emb=np.asarray(list(model.embed(texts,batch_size=24)))
 qv=np.asarray(list(model.query_embed(query))[0])
 semrank={int(i):r for r,i in enumerate(np.argsort(emb@qv)[::-1],1)}
 scored=[(1/(60+i)+1/(60+semrank[i-1]),x) for i,x in enumerate(b,1)]
 return [{**x,'hybrid_score':score} for score,x in sorted(scored,key=lambda v:-v[0])[:n]]
def main():
 qs=[json.loads(s) for s in (R/'questions_en.jsonl').open()]
 model=TextEmbedding(model_name='BAAI/bge-small-en-v1.5',cache_dir='./ftkb/models',threads=4)
 rows=[]
 for j,q in enumerate(qs,1):
  b=search(q['question'],60)
  if not b: top=[]
  else:
   texts=[x['title']+' '+x['text'][:1200] for x in b]
   emb=np.asarray(list(model.embed(texts,batch_size=24)))
   query=np.asarray(list(model.query_embed(q['question']))[0])
   sem=np.argsort(emb@query)[::-1]
   semrank={int(i):r for r,i in enumerate(sem,1)}
   scored=[(1/(60+i)+1/(60+semrank[i-1]),x) for i,x in enumerate(b,1)]
   top=[x for _,x in sorted(scored,key=lambda v:-v[0])[:5]]
  page=int(any(x['key']==q['answer_key'] and abs(x['page']-q['answer_page'])<=1 for x in top))
  paper=int(any(x['key']==q['answer_key'] for x in top))
  rows.append(dict(id=q['id'],topic=q['topic'],card=q['card'],key=q['answer_key'],page=q['answer_page'],hybrid_page5=page,hybrid_paper5=paper,hybrid_top5=[{'key':x['key'],'page':x['page']} for x in top]))
  if j%10==0:print('hybrid',j,flush=True)
 tag=sys.argv[1] if len(sys.argv)>1 else 'partial'
 with (R/f'hybrid_results_{tag}.jsonl').open('x') as f:
  for x in rows:f.write(json.dumps(x,ensure_ascii=False)+'\n')
 with (R/f'hybrid_metrics_{tag}.csv').open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['N','page_hits5','page_rate','paper_hits5','paper_rate','question_sha256']);w.writeheader();n=len(rows);p=sum(x['hybrid_page5'] for x in rows);k=sum(x['hybrid_paper5'] for x in rows)
  w.writerow(dict(N=n,page_hits5=p,page_rate=f'{p/n:.3f}',paper_hits5=k,paper_rate=f'{k/n:.3f}',question_sha256=hashlib.sha256((R/'questions_en.jsonl').read_bytes()).hexdigest()))
 print('hybrid',p,k,'/',n)
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='search':
  for x in hybrid_search(' '.join(sys.argv[2:])):
   print(f"{x['title']} ({x['year']}) Zotero key={x['key']} PDF p.{x['page']} score={x['hybrid_score']:.4f}\n  {x['text'][:350]}\n")
 else:main()
