"""Encode complete D2 text corpus with frozen MiniLM, two modalities."""
import argparse,hashlib,json,pathlib,subprocess
import numpy as np
from sentence_transformers import SentenceTransformer

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()

def push(p,remote,conf):
 q=subprocess.run(['rclone','lsjson',remote,'--config',str(conf)],capture_output=True,text=True)
 if q.returncode==0:raise RuntimeError('exists on Drive '+remote)
 subprocess.run(['rclone','copyto',str(p),remote,'--config',str(conf),'--tpslimit','5'],check=True)
 q=subprocess.run(['rclone','lsjson',remote,'--config',str(conf)],capture_output=True,text=True,check=True)
 items=json.loads(q.stdout);assert len(items)==1 and items[0]['Size']==p.stat().st_size
 print('ARCHIVED_EMBED',p.name,p.stat().st_size,sha(p),flush=True)

def main():
 p=argparse.ArgumentParser();p.add_argument('--text',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);p.add_argument('--drive',required=True);p.add_argument('--config',type=pathlib.Path,required=True);a=p.parse_args()
 assert (a.text/'text.done').exists();files=sorted(a.text.glob('text_*.jsonl'))
 assert len(files)==115,(len(files),)
 a.out.mkdir(exist_ok=True,parents=True)
 model=SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2',device='cuda');model.eval()
 total=0;manifest=[]
 for src in files:
  rows=[json.loads(x) for x in src.open()];n=len(rows)
  assert n and all(r['llm'] and r['template'] for r in rows)
  dest=a.out/(src.stem+'_embeddings.npz')
  if not dest.exists():
   v1=model.encode([r['llm'] for r in rows],batch_size=256,convert_to_numpy=True,show_progress_bar=False)
   v2=model.encode([r['template'] for r in rows],batch_size=256,convert_to_numpy=True,show_progress_bar=False)
   assert v1.shape==v2.shape==(n,384) and np.isfinite(v1).all() and np.isfinite(v2).all()
   with dest.open('xb') as f:np.savez_compressed(f,llm=v1.astype(np.float32),template=v2.astype(np.float32),initialization=np.array([r['initialization'] for r in rows]))
   push(dest,a.drive+'/'+dest.name,a.config)
  with np.load(dest) as z:assert z['llm'].shape==z['template'].shape==(n,384)
  manifest.append({'text':src.name,'text_sha256':sha(src),'embedding':dest.name,'embedding_sha256':sha(dest),'count':n})
  total+=n; print('EMBED',src.name,total,flush=True)
 assert total==58439
 m=a.out/'manifest_final.json';m.write_text(json.dumps({'count':total,'chunks':manifest,'model':'sentence-transformers/all-MiniLM-L6-v2'},indent=2));push(m,a.drive+'/'+m.name,a.config)
 (a.out/'embedding.done').write_text(json.dumps({'count':total,'sha256':sha(m)}))
 print('EMBED_DONE',total,flush=True)
if __name__=='__main__':main()
