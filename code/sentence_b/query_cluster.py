#!/usr/bin/env python3
"""Streaming global semantic retrieval and spherical k-means on frozen local sentence shards."""
import argparse, heapq, json, os, sqlite3, time
from pathlib import Path
import numpy as np
from fastembed import TextEmbedding
ROOT=Path.home()/'ftkb_sentences'; OUT=ROOT/'out'; SHARDS=ROOT/'shards'
MODEL='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'

def unit(x):return x/np.maximum(np.linalg.norm(x,axis=-1,keepdims=True),1e-9)
def embed_questions(questions):
    m=TextEmbedding(model_name=MODEL,cache_dir=str(Path.home()/'ftkb_figures/models'),threads=6,local_files_only=True)
    return unit(np.array(list(m.embed(questions,batch_size=8)),dtype=np.float32))
def search(questions,n=800):
    q=embed_questions(questions); tops=[[] for _ in q]; t=time.monotonic();total=0
    for j,meta in enumerate(sorted(SHARDS.glob('*.json'))):
        stem=meta.stem; count=json.loads(meta.read_text())['sentences'];total+=count
        if not count:continue
        mat=np.memmap(SHARDS/(stem+'.i8'),dtype=np.int8,shape=(count,384),mode='r')
        # Block bounded memory; int8 normalized embeddings, scores float dot/127.
        for a in range(0,count,8192):
            b=min(a+8192,count); scores=np.asarray(mat[a:b],dtype=np.float32)@q.T/127
            for qi in range(len(q)):
                col=scores[:,qi];take=min(n,len(col))
                idx=np.argpartition(col,-take)[-take:]
                for k in idx:
                    candidate=(float(col[k]),stem,a+int(k)+1)
                    if len(tops[qi])<n:heapq.heappush(tops[qi],candidate)
                    elif candidate[0]>tops[qi][0][0]:heapq.heapreplace(tops[qi],candidate)
        if j%30==0:print('searched shards',j+1,'sentences',total,'elapsed',round(time.monotonic()-t),flush=True)
    for qi,top in enumerate(tops):
        result=[]
        by_shard={}
        for score,stem,sid in sorted(top,reverse=True):by_shard.setdefault(stem,[]).append((score,sid))
        for stem,ids in by_shard.items():
            c=sqlite3.connect(f'file:{SHARDS/(stem+".sqlite")}?mode=ro',uri=True)
            for score,sid in ids:
                row=c.execute('select work,attachment,title,year,physical_page,sentence_no,is_ocr,library,text from sentences where sid=?',(sid,)).fetchone()
                if row: result.append(dict(score=score,stem=stem,sid=sid,work=row[0],attachment=row[1],title=row[2],year=row[3],physical_page=row[4],sentence_no=row[5],is_ocr=row[6],library=row[7],text=row[8]))
            c.close()
        result.sort(key=lambda x:x['score'],reverse=True)
        # Remove identical sentence reprints, preserve work diversity in reporting later.
        seen=set();ded=[]
        for item in result:
            key=' '.join(item['text'].lower().split())
            if key in seen:continue
            seen.add(key);ded.append(item)
        (OUT/f'B-{qi+1}_retrieved.json').write_text(json.dumps(dict(question=questions[qi],total_scanned=total,candidates=ded,seconds=time.monotonic()-t),ensure_ascii=False,indent=1))
        print('B',qi+1,'candidates',len(ded),'scanned',total,flush=True)

def kmeans(X,k,seed=20261016):
    rng=np.random.default_rng(seed);centers=[X[rng.integers(len(X))]]
    for _ in range(1,k):
        d=1-np.max([邮箱](centers).T,axis=1);d=np.maximum(d,0)**2
        centers.append(X[rng.choice(len(X),p=d/d.sum())] if d.sum()>0 else X[rng.integers(len(X))])
    C=np.array(centers)
    for _ in range(40):
        labels=np.argmax([邮箱],axis=1)
        new=np.array([X[labels==i].mean(axis=0) if np.any(labels==i) else C[i] for i in range(k)])
        new=unit(new)
        if np.max(np.abs(new-C))<1e-4:break
        C=new
    return labels,C

def silhouette(X,labels):
    rng=np.random.default_rng(20261016);take=rng.choice(len(X),min(250,len(X)),replace=False)
    D=1-X[take]@X.T; values=[]
    for local,i in enumerate(take):
        same=np.where(labels==labels[i])[0];same=same[same!=i]
        if len(same)==0:continue
        a=D[local,same].mean(); b=min(D[local,labels==j].mean() for j in set(labels) if j!=labels[i] and np.any(labels==j))
        values.append((b-a)/max(a,b,1e-6))
    return float(np.mean(values)) if values else -1

def cluster():
    for qi in range(1,4):
        data=json.loads((OUT/f'B-{qi}_retrieved.json').read_text());rows=data['candidates'];N=len(rows)
        X=np.zeros((N,384),dtype=np.float32)
        groups={}
        for i,r in enumerate(rows):groups.setdefault(r['stem'],[]).append((i,r['sid']))
        for stem,part in groups.items():
            size=json.loads((SHARDS/(stem+'.json')).read_text())['sentences']
            matrix=np.memmap(SHARDS/(stem+'.i8'),dtype=np.int8,shape=(size,384),mode='r')
            for i,sid in part:X[i]=matrix[sid-1].astype(np.float32)/127
        X=unit(X);best=None;tests=[]
        for k in range(3,min(9,N//10+1)):
            labels,C=kmeans(X,k);s=silhouette(X,labels);sizes=np.bincount(labels,minlength=k)
            tests.append(dict(k=k,silhouette=round(s,4),smallest=int(min(sizes))))
            if min(sizes)>=5 and (best is None or s>best[0]):best=(s,k,labels,C)
        if best is None:raise RuntimeError('too few candidates / all clusters tiny')
        _,k,labels,C=best; clusters=[]
        for j in range(k):
            idx=np.where(labels==j)[0]; idx=sorted(idx,key=lambda i:float(X[i]@C[j]),reverse=True)
            reps=[];works=set()
            for i in idx:
                r=rows[i];w=r['work'] or r['attachment']
                if w in works:continue
                reps.append(r);works.add(w)
                if len(reps)==5:break
            clusters.append(dict(cluster=j+1,size=len(idx),work_count=len({rows[i]['work'] or rows[i]['attachment'] for i in idx}),representatives=reps,member_ids=[int(i) for i in idx]))
        result=dict(question=data['question'],scanned=data['total_scanned'],retrieved=N,k=k,tests=tests,clusters=clusters)
        (OUT/f'B-{qi}_clusters.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        print('cluster',qi,'k',k,'sizes',[c['size'] for c in clusters],'tests',tests,flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['search','cluster']);a=p.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    if a.action=='search':search(['wind speed decrease increase climate change global terrestrial stilling recovery','mixed wind climates thunderstorm synoptic wind separate fitting pooled distribution long return period design wind speed','thunderstorm misclassification missed gust detection mixed climate extreme wind speed bias'])
    else:cluster()
