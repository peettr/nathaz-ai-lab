#!/usr/bin/env python3
"""FTS5 BM25 candidate generation, multilingual MiniLM reranking (no download)."""
import argparse,os,re,sqlite3
import numpy as np
from fastembed import TextEmbedding

MODEL='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
CACHE='./services/ftkb/data/models'
GLOSS={'下击暴流':'downburst','台风':'typhoon','风速':'wind speed','剖面':'profile','阵风':'gust','湍流':'turbulence','压力':'pressure','建筑':'building','载荷':'load','振动':'vibration','系数':'coefficient','分布':'distribution','风场':'wind field'}

def search(db,query,top):
    c=sqlite3.connect(f'file:{db}?mode=ro',uri=True)
    # FTS5 unicode61 cannot segment Chinese or translate it: bridge candidates with a fixed domain glossary,
    # then semantic rerank with multilingual vectors. For unknown Chinese terms, bounded scan fallback.
    translated=' '.join(v for k,v in GLOSS.items() if k in query)
    terms=re.findall(r'[A-Za-z]{3,}',query+' '+translated)
    ids=[];scores={}
    if terms:
        expr=' OR '.join('"'+x.replace('"','')+'"' for x in terms)
        legacy=any(x[1]=='fig_id' for x in c.execute('PRAGMA table_info(captions_fts)'))
        sql=('SELECT fig_id,bm25(captions_fts) FROM captions_fts WHERE captions_fts MATCH ? ORDER BY bm25(captions_fts) LIMIT 300' if legacy else
             'SELECT f.fig_id,bm25(captions_fts) FROM captions_fts JOIN figures f ON f.rowid=captions_fts.rowid WHERE captions_fts MATCH ? ORDER BY bm25(captions_fts) LIMIT 300')
        for fid,rank in c.execute(sql,(expr,)):
            ids.append(fid);scores[fid]=rank
    if ids:
        slots=','.join('?'*len(ids))
        rows=c.execute(f'SELECT fig_id,source_library,doc_id,physical_page,fig_label,caption_text,thumb_path FROM figures WHERE fig_id IN ({slots})',ids).fetchall()
    else:
        rows=c.execute('SELECT fig_id,source_library,doc_id,physical_page,fig_label,caption_text,thumb_path FROM figures WHERE caption_text IS NOT NULL ORDER BY fig_id LIMIT 300').fetchall()
    c.close()
    if not rows:return []
    # Require a cached snapshot: fastembed can otherwise silently download.
    snapshot=os.path.join(CACHE,'models--Qdrant--paraphrase-multilingual-MiniLM-L12-v2-onnx-Q','snapshots')
    if not os.path.isdir(snapshot):raise RuntimeError('MiniLM cache missing; no downloads permitted')
    model=TextEmbedding(model_name=MODEL,cache_dir=CACHE,threads=2,local_files_only=True)
    q=np.asarray(list(model.embed([query]))[0]);v=np.asarray(list(model.embed([r[5][:600] for r in rows])))
    sim=(v@q)/(np.linalg.norm(v,axis=1)*np.linalg.norm(q)+1e-12)
    ranked=sorted(zip(sim,rows),key=lambda x:x[0],reverse=True)[:top]
    return [(round(float(s),4),)+r for s,r in ranked]

def main():
    p=argparse.ArgumentParser();p.add_argument('question');p.add_argument('--top',type=int,default=5);p.add_argument('--db',default='./ftkb_figures/figures.sqlite');a=p.parse_args()
    for r in search(a.db,a.question,a.top):print(f'{r[0]:.3f}\t{r[1]}\t{r[2]}\tp{r[3]}\t{r[4]}\t{r[5][:200]}\t{r[6]}')
if __name__=='__main__':main()
