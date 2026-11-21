import subprocess,sys,time
print('Installing vLLM pinned Torch CUDA12 stack',flush=True)
p=subprocess.run([sys.executable,'-m','pip','install','--upgrade','torch==2.9.0','torchvision==0.24.0','torchaudio==2.9.0'],capture_output=True,text=True)
print('EXIT',p.returncode,p.stdout[-3500:],p.stderr[-3500:],flush=True)
if p.returncode:raise RuntimeError('install failed')
