"""Bounded, resumable D2 local-vLLM generation; immutable chunks on Drive."""
import argparse, hashlib, json, pathlib, random, re, subprocess, time

def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()

def upload(path,remote,conf):
 # copyto never replaces a prior Drive object; check by listing first.
 check=subprocess.run(['rclone','lsjson',remote,'--config',str(conf)],capture_output=True,text=True)
 if check.returncode==0:
  raise RuntimeError('remote artifact already exists: '+remote)
 subprocess.run(['rclone','copyto',str(path),remote,'--config',str(conf),'--drive-chunk-size','64M','--tpslimit','5','--retries','3'],check=True)
 info=subprocess.run(['rclone','lsjson',remote,'--config',str(conf)],capture_output=True,text=True,check=True)
 entries=json.loads(info.stdout);assert len(entries)==1,(remote,entries)
 meta=entries[0]
 assert meta['Size']==path.stat().st_size,(remote,meta)
 if meta.get('Hashes',{}).get('MD5'):
  import hashlib as _h
  assert meta['Hashes']['MD5']==_h.md5(path.read_bytes()).hexdigest(),remote
 print('ARCHIVED',path.name,path.stat().st_size,digest(path),flush=True)

def values(s):
 o=[]
 def scan(x):
  if isinstance(x,dict):
   for v in x.values():scan(v)
  elif isinstance(x,(float,int)):o.append(float(x))
 scan(s);return o
NUM=re.compile(r'(?<![\w.])[-+]?\d+(?:\.\d+)?(?![\w.])')
COORD=re.compile(r'[-+]?\d+(?:\.\d+)?°N,?\s*[-+]?\d+(?:\.\d+)?°E')
def audit(row):
 s=row['summary']; text=row['llm']; allowed=values(s)
 coords={v['location'].replace(' ','') for k,v in s.items() if isinstance(v,dict) and 'location' in v}
 invalid_coord=[x for x in COORD.findall(text) if x.replace(' ','') not in coords]
 # Numbers from coordinate tokens are removed; weather-level and interval literals are allowed.
 stripped=COORD.sub(' ',text)
 errors=[]
 for m in NUM.finditer(stripped):
  tok=m.group();val=float(tok)
  if val in (500,850,10,2,6,1979,2015):continue
  if any(abs(val-v)<1e-5 for v in allowed):continue
  # Explicit 'negative X' and 'cool X' are signed despite positive typography.
  prefix=stripped[max(0,m.start()-18):m.start()].lower()
  if re.search(r'(?:negative|cool|minus)\s+$',prefix) and any(abs(-val-v)<1e-5 for v in allowed):continue
  errors.append(tok)
 # Bind a high/low to its own clause; do not confuse the gradient maximum.
 roles=[]
 for label,key in [('maximum','z500_max'),('minimum','z500_min')]:
  for m in re.finditer(r'\b'+label+r'\b',text,re.I):
   lead=text[max(0,m.start()-45):m.start()].lower()
   if not ('height' in lead or 'geopotential' in lead):continue
   frag=re.split(r'\.(?:\s|$)',text[m.end():min(len(text),m.end()+100)])[0]
   match=COORD.search(frag)
   if match and match.group().replace(' ','')!=s[key]['location'].replace(' ',''):roles.append(label+':'+match.group())
 wc=len(text.split())
 return {'initialization':row['initialization'],'numbers_not_in_summary':errors,'coordinates_not_in_summary':invalid_coord,'height_role_mismatch':roles,'word_count':wc,'finish_reason':row['finish_reason'],'strict_match':not(errors or invalid_coord or roles),'word_range_ok':60<=wc<=120}

def main():
 p=argparse.ArgumentParser();p.add_argument('--inputs',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);p.add_argument('--drive',required=True);p.add_argument('--config',type=pathlib.Path,required=True);p.add_argument('--batch',type=int,default=512)
 p.add_argument('--pilot-batches',type=int,default=0);a=p.parse_args()
 assert a.batch>=256
 a.out.mkdir(parents=True,exist_ok=True)
 files=sorted(a.inputs.glob('inputs_*.jsonl'));assert len(files)==58
 import torch
 from vllm import LLM,SamplingParams
 random.seed(31026);torch.manual_seed(31026)
 llm=LLM(model='Qwen/Qwen2.5-7B-Instruct',trust_remote_code=False,dtype='float16',max_model_len=2048,gpu_memory_utilization=0.85,seed=31026,enforce_eager=True)
 tok=llm.get_tokenizer()
 sample_rng=random.Random(31026); sample_ids=set(sample_rng.sample(range(58439),200));checks=[];total=0;chunk_index=0;start_clock=time.monotonic()
 for source in files:
  rows=[json.loads(line) for line in source.open()]
  for j in range(0,len(rows),a.batch):
   part=rows[j:j+a.batch];dst=a.out/f'text_{chunk_index:04d}.jsonl';ch=a.out/f'checks_{chunk_index:04d}.json'
   if dst.exists() and ch.exists():
    saved=[json.loads(x) for x in dst.open()]; assert len(saved)==len(part) and all(x['initialization']==y['initialization'] for x,y in zip(saved,part))
    checks.extend(json.loads(ch.read_text()));total+=len(part);chunk_index+=1;continue
   assert not dst.exists() and not ch.exists()
   prompts=[tok.apply_chat_template([{'role':'user','content':r['prompt']}],tokenize=[已隐去],add_generation_prompt=True) for r in part]
   t0=time.monotonic();outputs=llm.generate(prompts,SamplingParams(temperature=0,top_p=1,max_tokens=[已隐去],seed=31026))
   for r,o in zip(part,outputs):
    r['llm']=o.outputs[0].text.strip();r['finish_reason']=o.outputs[0].finish_reason;r.pop('prompt')
   with dst.open('x') as f:
    for r in part:f.write(json.dumps(r,ensure_ascii=False)+'\n')
   c=[audit(r) for ix,r in enumerate(part,start=total) if ix in sample_ids]
   ch.write_text(json.dumps(c,ensure_ascii=False));checks.extend(c)
   upload(dst,a.drive+'/'+dst.name,a.config);upload(ch,a.drive+'/'+ch.name,a.config)
   print('BATCH',chunk_index,'rows',len(part),'sec',round(time.monotonic()-t0,2),'total',total+len(part),flush=True)
   total+=len(part);chunk_index+=1
   if a.pilot_batches and chunk_index>=a.pilot_batches:
    (a.out/'pilot.done').write_text(json.dumps({'count':total,'batches':chunk_index,'elapsed_sec':time.monotonic()-start_clock}))
    print('PILOT_DONE',total,flush=True);return
 assert total==58439 and len(checks)==200
 report={'count':total,'sample_count':len(checks),'strict_match_count':sum(c['strict_match'] for c in checks),'word_range_ok_count':sum(c['word_range_ok'] for c in checks),'checks':checks,'gpu':torch.cuda.get_device_name(0)}
 path=a.out/'audit_200.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2));upload(path,a.drive+'/'+path.name,a.config)
 (a.out/'text.done').write_text(json.dumps({'count':total,'audit_sha256':digest(path)}))
 print('TEXT_DONE',total,report['strict_match_count'],flush=True)
if __name__=='__main__':main()
