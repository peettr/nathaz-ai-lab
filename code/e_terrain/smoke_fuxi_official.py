#!/usr/bin/env python3
"""Smoke-test only author's official FuXi-CFD ONNX and official sample, not Swiss validation."""
import requests,hashlib,subprocess,sys,os,time
from pathlib import Path
BASE='https://huggingface.co/linchensen/FuXi-CFD-model/resolve/98d2cb643ebddb752803919ad65eb2457314a2ae/'
ROOT=Path('/content/e_terrain/fuxi_official')
paths=['fuxicfd-model/model/fuxicfd_model.onnx','fuxicfd-model/inference_example/scripts/infer.py','fuxicfd-model/inference_example/data/inputs.npz','fuxicfd-model/inference_example/normalization/scaler_input.npy','fuxicfd-model/inference_example/normalization/scaler_output.npy','fuxicfd-model/inference_example/utils/io.py','fuxicfd-model/inference_example/utils/preprocessing.py','fuxicfd-model/inference_example/utils/postprocessing.py']
for path in paths:
 p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():print('ALREADY',path,p.stat().st_size,flush=True);continue
 with requests.get(BASE+path+'?download=true',timeout=(30,300),stream=True) as r:
  r.raise_for_status();h=hashlib.sha256();n=0
  with p.open('xb') as f:
   for chunk in r.iter_content(2**20):
    f.write(chunk);h.update(chunk);n+=len(chunk)
    if n and n%(100*2**20)<2**20:print('DOWNLOADED_MB',path,n//2**20,flush=True)
 print('DOWNLOADED',path,n,h.hexdigest(),flush=True)
 if path.endswith('.onnx'):assert n==889406671 and h.hexdigest()=='13daae67371d20a7ffb00db0a6c4679e580c28e77d2521eb7c2dcf9e80f20b3e'
script=ROOT/'fuxicfd-model/inference_example/scripts/infer.py'
cmd=[sys.executable,str(script),'--model',str(ROOT/paths[0]),'--input',str(ROOT/paths[2]),'--output','/content/e_terrain/fuxi_official_sample_prediction.npz']
t=time.monotonic();x=subprocess.run(cmd,capture_output=True,text=True,timeout=300)
print('INFERENCE',x.returncode,'elapsed_sec',time.monotonic()-t,'stdout',x.stdout[-1000:],'stderr',x.stderr[-1500:],flush=True)
assert x.returncode==0
