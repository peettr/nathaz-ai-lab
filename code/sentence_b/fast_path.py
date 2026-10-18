#!/usr/bin/env python3
"""Local FTS candidate-page sentence experiment; no network or source writes."""
import json, sqlite3, time, os, sys, re
from pathlib import Path
import numpy as np
from fastembed import TextEmbedding
from sentence_pipeline import sentences
from query_cluster import unit,kmeans,silhouette
ROOT=Path.home()/'ftkb_sentences'; OUT=ROOT/'fast'; OUT.mkdir(exist_ok=True)
MODEL='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
TERMS=[
 ('B-1','wind speed decrease increase climate change global terrestrial stilling recovery', ['"climate change" wind','"wind speed" climate','"terrestrial stilling"','"wind speed" trend','"wind speed" future']),
 ('B-2','mixed wind climates thunderstorm synoptic wind separate fitting pooled distribution long return period design wind speed',['thunderstorm synoptic wind','thunderstorm extreme wind','mixed wind climate','thunderstorm return period','non thunderstorm design wind']),
 ('B-3','thunderstorm misclassification missed gust detection mixed climate extreme wind speed bias',['thunderstorm classification','thunderstorm misclassification','thunderstorm detection gust','thunderstorm missed events','thunderstorm extreme bias'])]

def getpages(c,queries,limit=3000):
    scores={}
    for s in queries:
        query=' OR '.join('"'+t.replace('"','').replace('-',' ')+'"' for t in s.split() if len(t)>3)
        try: rows=c.execute('SELECT rowid,bm25(page_fts) FROM page_fts WHERE page_fts MATCH ? ORDER BY bm25(page_fts) LIMIT 2400',(query,)).fetchall()
        except sqlite3.OperationalError as e:print('FTS ERROR',s,e,flush=True);continue
        for rank,(pid,score) in enumerate(rows): scores[pid]=scores.get(pid,0)+1/(60+rank)
    ids=[i for i,_ in sorted(scores.items(),key=lambda x:-x[1])[:limit]]
    return ids

def run():
    c=sqlite3.connect(f'file:{ROOT}/input/index.sqlite?mode=ro',uri=True);c.row_factory=sqlite3.Row
    m=TextEmbedding(model_name=MODEL,cache_dir=str(Path.home()/'ftkb_figures/models'),threads=6,local_files_only=True)
    for name,question,terms in TERMS:
        start=time.monotonic();dest=OUT/name;dest.mkdir(exist_ok=True)
        if (dest/'DONE.json').exists():print(name,'already completed',flush=True);continue
        ids=getpages(c,terms)
        print(name,'candidate_pages',len(ids),flush=True)
        records=[]
        for base in range(0,len(ids),400):
            marks=','.join('?'*len(ids[base:base+400]))
            for p in c.execute(f'SELECT p.*,a.library FROM pages p LEFT JOIN attachments a ON a.attachment=p.attachment WHERE p.id IN ({marks})',ids[base:base+400]):
                for no,text in enumerate(sentences(p['text'] or ''),1):
                    records.append(dict(page_id=p['id'],work=p['work'],attachment=p['attachment'],title=p['title'],year=p['year'],physical_page=p['page'],sentence_no=no,is_ocr=int(p['text_source']=='ocr'),library=p['library'],text=text))
        print(name,'sentences',len(records),flush=True)
        # Preserve complete candidate dataset; restart only after complete marker.
        (dest/'pages.json').write_text(json.dumps(ids))
        with open(dest/'sentences.jsonl','w') as f:
            for r in records:f.write(json.dumps(r,ensure_ascii=False)+'\n')
        q=unit(np.asarray(list(m.embed([question],batch_size=1)),dtype=np.float32))[0]
        heap=[]; import heapq
        count=0
        with open(dest/'vectors.i8.part','wb') as f:
            for base in range(0,len(records),128):
                chunk=records[base:base+128]
                embeddings=np.asarray(list(m.embed([r['text'] for r in chunk],batch_size=64)),dtype=np.float32)
                embeddings=unit(embeddings)
                f.write(np.clip(np.rint(embeddings*127),-127,127).astype(np.int8).tobytes())
                scores=embeddings@q
                for j,score in enumerate(scores):
                    key=(float(score),base+j)
                    if len(heap)<1000:heapq.heappush(heap,key)
                    elif score>heap[0][0]:heapq.heapreplace(heap,key)
                count+=len(chunk)
                if count%8192<128:print(name,'encoded',count, 'elapsed',round(time.monotonic()-start),flush=True)
        os.replace(dest/'vectors.i8.part',dest/'vectors.i8')
        selected=sorted(heap,reverse=True)
        seen=set();ded=[]
        for score,i in selected:
            text=' '.join(records[i]['text'].lower().split())
            if text not in seen:seen.add(text);ded.append((score,i))
            if len(ded)>=800:break
        mat=np.memmap(dest/'vectors.i8',dtype=np.int8,mode='r',shape=(len(records),384))
        X=unit(np.array([mat[i].astype(np.float32)/127 for score,i in ded]))
        tests=[];best=None
        for k in range(3,9):
            labels,C=kmeans(X,k);v=silhouette(X,labels);sizes=np.bincount(labels,minlength=k)
            tests.append(dict(k=k,silhouette=round(v,4),smallest=int(min(sizes))))
            if min(sizes)>=5 and (best is None or v>best[0]):best=(v,k,labels,C)
        if best is None:raise RuntimeError('no valid clustering')
        _,k,labels,C=best;clusters=[]
        for j in range(k):
            indexes=np.where(labels==j)[0];ordered=sorted(indexes,key=lambda i:float(X[i]@C[j]),reverse=True)
            reps=[];works=set()
            for i in ordered:
                r=records[ded[i][1]];w=r['work'] or r['attachment']
                if w in works:continue
                reps.append(dict(**r,score=ded[i][0]));works.add(w)
                if len(reps)==5:break
            clusters.append(dict(cluster=j+1,size=len(indexes),work_count=len({records[ded[i][1]]['work'] or records[ded[i][1]]['attachment'] for i in indexes}),representatives=reps))
        result=dict(question=question,route='FTS BM25 candidate pages then MiniLM sentences',candidate_pages=len(ids),sentences=len(records),retrieved=len(ded),k=k,tests=tests,clusters=clusters,seconds=time.monotonic()-start)
        (dest/'clusters.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        (dest/'DONE.json').write_text(json.dumps(dict(seconds=result['seconds'],page_count=len(ids),sentence_count=len(records))))
        print('DONE',name,'seconds',round(result['seconds']),flush=True)
if __name__=='__main__':run()
