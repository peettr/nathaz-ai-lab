#!/usr/bin/env python3
"""CPU BGE-small embeddings of physical PDF pages and hybrid retrieval."""
import argparse,json,sqlite3,sys
from pathlib import Path
import numpy as np
from fastembed import TextEmbedding
sys.path.insert(0,str(Path(__file__).parent))
from ftkb import DB,search
OUT=Path('./ftkb/vectors');OUT.mkdir(exist_ok=True)
MODEL='BAAI/bge-small-en-v1.5'
def embedder():return TextEmbedding(model_name=MODEL,cache_dir='./ftkb/models',threads=4)
def build(batch=128):
 c=sqlite3.connect(f'file:{DB}?mode=ro',uri=True)
 existing=set()
 for p in OUT.glob('ids_*.npy'):existing.update(np.load(p).tolist())
 m=embedder();n=0
 cur=c.execute('SELECT id,title,text FROM pages ORDER BY id')
 while True:
  rows=[]
  while len(rows)<batch:
   x=cur.fetchone()
   if x is None:break
   if x[0] not in existing:rows.append(x)
  if not rows:break
  ids=np.array([x[0] for x in rows],dtype=np.int32)
  txt=[x[1]+' '+x[2][:1200] for x in rows]
  vec=np.asarray(list(m.embed(txt,batch_size=32)),dtype=np.float16)
  start=ids[0];np.save(OUT/f'ids_{start}.npy',ids);np.save(OUT/f'vec_{start}.npy',vec)
  n+=len(rows)
  if n%2048==0:print('embedded new',n,flush=True)
 print('new embeddings',n,flush=True)
_MODEL=None
_VECTORS=None
def vector(query,limit=100):
 global _MODEL,_VECTORS
 if _MODEL is None:_MODEL=embedder()
 v=np.asarray(list(_MODEL.query_embed(query))[0],dtype=np.float32)
 if _VECTORS is None:
  ids=[];vec=[]
  for p in OUT.glob('ids_*.npy'):
   ids.append(np.load(p));vec.append(np.load(OUT/p.name.replace('ids_','vec_')).astype(np.float32))
  _VECTORS=(np.concatenate(ids),np.concatenate(vec)) if ids else (np.array([],dtype=np.int32),np.empty((0,384),dtype=np.float32))
 ids,mat=_VECTORS
 if len(ids)==0:return []
 scores=mat@v;top=np.argsort(scores)[-min(limit,len(scores)):][::-1]
 candidates=[(float(scores[i]),int(ids[i])) for i in top]
 c=sqlite3.connect(f'file:{DB}?mode=ro',uri=True);c.row_factory=sqlite3.Row
 out=[]
 for score,id in candidates:
  row=c.execute('select * from pages where id=?',(id,)).fetchone()
  if row:out.append({**dict(row),'score':score})
 return out
def hybrid(query,n=5):
 b=search(query,100);v=vector(query,100)
 rr={}
 for rows in (b,v):
  for rank,x in enumerate(rows,1):rr[x['id']]=rr.get(x['id'],0)+1/(60+rank)
 entries={x['id']:x for x in b+v}
 return [{**entries[id],'hybrid_score':score} for id,score in sorted(rr.items(),key=lambda x:-x[1])[:n]]
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('cmd',choices=['build','search']);p.add_argument('query',nargs='?');p.add_argument('-n',type=int,default=5);a=p.parse_args()
 if a.cmd=='build':build()
 else:
  for x in hybrid(a.query,a.n):print(f"{x['title']} ({x['year']}) key={x['key']} PDF p.{x['page']} score={x['hybrid_score']:.4f}\n  {x['text'][:350]}\n")
