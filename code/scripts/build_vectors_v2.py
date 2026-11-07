#!/usr/bin/env python3
"""Precompute multilingual caption embeddings for *all* searchable figures."""
import argparse,sqlite3,json,os
from pathlib import Path
import numpy as np
from fastembed import TextEmbedding
MODEL='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
CACHE='./services/ftkb/data/models'
def main():
 p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--out',required=True);a=p.parse_args()
 if Path(a.out+'.npy').exists() or Path(a.out+'.json').exists():raise FileExistsError('refusing overwrite')
 if not Path(CACHE,'models--Qdrant--paraphrase-multilingual-MiniLM-L12-v2-onnx-Q','snapshots').is_dir():raise RuntimeError('cache missing; no download')
 c=sqlite3.connect('file:'+a.db+'?mode=ro',uri=True)
 rows=c.execute("SELECT fig_id,caption_text FROM figures WHERE caption_text IS NOT NULL AND kind!='table' AND caption_text NOT GLOB '表*' AND caption_text NOT LIKE 'Table %' ORDER BY fig_id").fetchall();c.close()
 model=TextEmbedding(model_name=MODEL,cache_dir=CACHE,threads=2,local_files_only=True)
 arr=[]
 for vec in model.embed([r[1][:600] for r in rows],batch_size=64):
  v=np.asarray(vec,dtype=np.float32);v/=max(np.linalg.norm(v),1e-12);arr.append(np.clip(np.rint(v*127),-127,127).astype(np.int8))
 Path(a.out).parent.mkdir(parents=True,exist_ok=True)
 np.save(a.out+'.npy',np.stack(arr));Path(a.out+'.json').write_text(json.dumps([r[0] for r in rows]))
 print('vectors',len(rows),'dim',len(arr[0]),'bytes',os.path.getsize(a.out+'.npy')+os.path.getsize(a.out+'.json'))
if __name__=='__main__':main()
