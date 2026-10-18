#!/usr/bin/env python3
"""A2 local-only CLIP CPU image index, resumable chunks and query cards."""
import argparse, csv, json, os, sqlite3, time, hashlib
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
import onnxruntime as ort
from tokenizers import Tokenizer
ROOT=Path.home()/"ftkb_figures"
FULL=ROOT/"full_v2"; OUT=FULL/"img_vectors"; MODEL=ROOT/"models"/"a2_clip"
QROOT=ROOT/"a2"/"queries"; RROOT=ROOT/"a2"/"results"
MEAN=np.array([.48145466,.4578275,.40821073],dtype=np.float32)[None,None,:]
STD=np.array([.26862954,.26130258,.27577711],dtype=np.float32)[None,None,:]

def preprocess(p):
    with Image.open(p) as im:
        im=im.convert('RGB'); w,h=im.size
        nw,nh=round(w*224/min(w,h)),round(h*224/min(w,h))
        im=im.resize((nw,nh),Image.Resampling.BICUBIC)
        left=(nw-224)//2; top=(nh-224)//2
        im=im.crop((left,top,left+224,top+224))
        a=np.asarray(im,dtype=np.float32)/255.
    return np.transpose((a-MEAN)/STD,(2,0,1))

def session(file,threads):
    o=ort.SessionOptions();o.intra_op_num_threads=threads;o.inter_op_num_threads=1
    return ort.InferenceSession(str(file),sess_options=o,providers=['CPUExecutionProvider'])

def rows():
    db=sqlite3.connect(f'file:{FULL}/figures_full.sqlite?mode=ro',uri=True)
    r=db.execute('SELECT fig_id,source_library,physical_page,caption_text,thumb_path FROM figures ORDER BY fig_id').fetchall()
    db.close();return r

def normalize(a):
    return a/np.maximum(np.linalg.norm(a,axis=1,keepdims=True),1e-8)

def encode(args):
    OUT.mkdir(parents=True,exist_ok=True); rr=rows()
    print('ROWS',len(rr),'START',time.strftime('%F %T'),flush=True)
    assert len(rr)==386894 and len(set(x[0] for x in rr))==len(rr)
    s=session(MODEL/'onnx/vision_model_uint8.onnx',args.threads)
    n=len(rr); started=time.time(); errors=[]; done=0
    for lo in range(0,n,args.chunk):
        dest=OUT/f'chunk_{lo:06d}.npz'; hi=min(n,lo+args.chunk)
        if dest.exists():
            with np.load(dest) as z:
                assert z['ids'].tolist()==[x[0] for x in rr[lo:hi]] and z['vec'].shape==(hi-lo,512)
            done+=hi-lo;continue
        vectors=np.zeros((hi-lo,512),np.float16); ids=np.array([x[0] for x in rr[lo:hi]],dtype='U32')
        for st in range(lo,hi,args.batch):
            ins=[];idx=[]
            for k in range(st,min(st+args.batch,hi)):
                try:ins.append(preprocess(FULL/'thumbs'/rr[k][4]));idx.append(k-lo)
                except Exception as e:errors.append([rr[k][0],str(e)[:180]])
            if ins:
                y=s.run(None,{'pixel_values':np.stack(ins)})[0]
                vectors[idx]=normalize(y).astype(np.float16)
        tmp=dest.with_name(dest.name+'.tmp')
        with open(tmp,'wb') as f:np.savez(f,ids=ids,vec=vectors)
        os.replace(tmp,dest);done=hi
        if errors:
            with open(OUT/'errors.jsonl','a') as f:
                for e in errors:f.write(json.dumps(e,ensure_ascii=False)+'\n')
            errors=[]
        dt=time.time()-started
        print('PROGRESS',done,n,'new_seconds',round(dt,1),'new_rate',round((done-lo)/dt,2) if dt else 0,'time',time.strftime('%F %T'),flush=True)
        if args.limit and done>=args.limit:break
    if done==n:
        (OUT/'DONE.json').write_text(json.dumps({'count':n,'seconds_this_invocation':time.time()-started,'model':'Xenova/clip-vit-base-patch32@d15189d vision_uint8','finished':time.strftime('%F %T')}))
        print('DONE',n,flush=True)

def text_embed(sess,tok,text):
    t=tok.encode(text);tokens=[已隐去]
    if len(tokens)<77:tokens += [0]*(77-len(tokens))
    x=sess.run(None,{'input_ids':np.array([tokens],dtype=np.int64)})[0]
    return normalize(x.astype(np.float32))[0]

def make_card(query,hits,dest,mode):
    width=1120;tile_w=520;tile_h=185
    canvas=Image.new('RGB',(width,190+5*tile_h),'white');d=ImageDraw.Draw(canvas)
    with Image.open(query) as im:
        pic=ImageOps.contain(im.convert('RGB'),(360,160));canvas.paste(pic,(10,10))
    d.text((380,20),f'{query.stem} {mode} | top 10',fill='black')
    for k,(score,r) in enumerate(hits):
        col=k%2;line=k//2;x=10+col*550;y=190+line*tile_h
        p=FULL/'thumbs'/r[4]
        try:
            with Image.open(p) as im:im=ImageOps.contain(im.convert('RGB'),(250,130));canvas.paste(im,(x,y))
        except Exception:d.text((x,y),'IMAGE READ ERROR',fill='red')
        d.text((x+255,y),f'#{k+1} {score:.3f} {r[1]} p{r[2]}',fill='black')
        caption=(r[3] or '')[:80].replace('\n',' ')
        # Pillow's default font is not guaranteed to render Chinese; CSV retains raw caption.
        lines=[caption[i:i+30] for i in range(0,len(caption),30)][:4]
        for j,part in enumerate(lines):
            try:d.text((x+255,y+22+j*24),part,fill='black')
            except UnicodeEncodeError:d.text((x+255,y+22+j*24),part.encode('ascii','replace').decode(),fill='black')
    canvas.save(dest,quality=80,optimize=True)

def query(args):
    rr=rows(); chunks=sorted(OUT.glob('chunk_*.npz'))
    assert (OUT/'DONE.json').exists() and sum(len(np.load(c)['ids']) for c in chunks)==len(rr)
    assert len(list(QROOT.glob('q*.png')))==10
    s=session(MODEL/'onnx/vision_model_uint8.onnx',args.threads)
    ts=session(MODEL/'onnx/text_model_int8.onnx',args.threads)
    tok=Tokenizer.from_file(str(MODEL/'tokenizer.json'));RROOT.mkdir(parents=True,exist_ok=True)
    definitions=json.loads((QROOT/'text_queries.json').read_text())
    for qpath in sorted(QROOT.glob('q*.png')):
        qid=qpath.stem[:3];start=time.time()
        vi=normalize(s.run(None,{'pixel_values':preprocess(qpath)[None]})[0])[0]
        vt=text_embed(ts,tok,definitions[qid]);best={'img':[],'text':[]}
        for path in chunks:
            with np.load(path) as z:
                ids=z['ids'];vec=z['vec'].astype(np.float32)
                idx0=int(path.stem.split('_')[1]);assert ids.tolist()==[x[0] for x in rr[idx0:idx0+len(ids)]]
                for mode,v in [('img',vi),('text',vt)]:
                    score=vec@v
                    take=np.argpartition(score,-10)[-10:]
                    best[mode].extend((float(score[k]),idx0+int(k)) for k in take)
                    best[mode]=sorted(best[mode],key=lambda x:-x[0])[:10]
        for mode in ('img','text'):
            hits=[(sc,rr[idx]) for sc,idx in best[mode]]
            name=qid+('_text_top10' if mode=='text' else '_top10')
            with open(RROOT/(name+'.csv'),'w',newline='') as f:
                w=csv.writer(f);w.writerow(['rank','score','fig_id','source_library','physical_page','caption_text','thumb_path'])
                for k,(sc,r) in enumerate(hits,1):w.writerow([k,sc,*r])
            make_card(qpath,hits,RROOT/(name+'.jpg'),mode)
        print('QUERY',qid,'seconds',round(time.time()-start,2),'image_top',best['img'][0],'text_top',best['text'][0],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['encode','query']);p.add_argument('--threads',type=int,default=8);p.add_argument('--batch',type=int,default=24);p.add_argument('--chunk',type=int,default=4096);p.add_argument('--limit',type=int,default=0)
    a=p.parse_args();{'encode':encode,'query':query}[a.action](a)
