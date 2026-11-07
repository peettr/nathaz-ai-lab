#!/usr/bin/env python3
"""Full-corpus MiniLM cosine search with FTS5 BM25 auxiliary score; no candidate cap."""
import argparse,os,re,sqlite3,json
import numpy as np
from fastembed import TextEmbedding
MODEL='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
CACHE=os.environ.get('A1_MODEL_CACHE',str(__import__('pathlib').Path.home()/'ftkb_figures/models'))
def search(db,prefix,question,top):
 c=sqlite3.connect('file:'+db+'?mode=ro',uri=True)
 ids=json.load(open(prefix+'.json'));v=np.load(prefix+'.npy',mmap_mode='r')
 if len(ids)!=len(v):raise ValueError('vector/id count mismatch')
 n=c.execute("SELECT count(*) FROM figures WHERE caption_text IS NOT NULL AND kind!='table' AND caption_text NOT GLOB '表*' AND caption_text NOT LIKE 'Table %'").fetchone()[0]
 if len(ids)!=n:raise ValueError('stale vector index')
 if not os.path.isdir(os.path.join(CACHE,'models--Qdrant--paraphrase-multilingual-MiniLM-L12-v2-onnx-Q','snapshots')):raise RuntimeError('model missing')
 model=TextEmbedding(model_name=MODEL,cache_dir=CACHE,threads=2,local_files_only=True)
 q=np.asarray(next(model.embed([question])),dtype=np.float32);q/=max(np.linalg.norm(q),1e-12)
 # Every indexed caption participates in semantic recall; BM25 is only a small tie-breaker.
 sim=np.asarray(v,dtype=np.float32)@q/127.0
 words=re.findall(r'[A-Za-z]{3,}',question)
 boosts={}
 if words:
  expr=' OR '.join('"'+w+'"' for w in words)
  for fid,bm in c.execute("SELECT f.fig_id,bm25(captions_fts) FROM captions_fts JOIN figures f ON f.rowid=captions_fts.rowid WHERE captions_fts MATCH ? AND f.kind!='table' ORDER BY bm25(captions_fts) LIMIT 1000",(expr,)):
   boosts[fid]=min(0.03,0.01/(1+max(0,bm)))
 idx=sorted(range(len(ids)),key=lambda i:float(sim[i])+boosts.get(ids[i],0),reverse=True)[:top]
 rows=[]
 for i in idx:
  r=c.execute('SELECT fig_id,source_library,physical_page,fig_label,caption_text,thumb_path,kind FROM figures WHERE fig_id=?',(ids[i],)).fetchone()
  rows.append((round(float(sim[i]),4),)+r)
 c.close();return rows
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('question');p.add_argument('--top',type=int,default=5);p.add_argument('--db',required=True);p.add_argument('--vectors',required=True);a=p.parse_args()
 for r in search(a.db,a.vectors,a.question,a.top):print(f'{r[0]:.3f}\t{r[1]}\t{r[2]}\tp{r[3]}\t{r[4]}\t{r[5][:160]}\t{r[7]}')
