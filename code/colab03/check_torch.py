import subprocess,os
p='/content/l264a100/venv/bin/python'
r=subprocess.run([p,'-c','import torch;print(torch.__version__,torch.version.cuda,torch.cuda.is_available(),torch.cuda.device_count())'],capture_output=True,text=True,timeout=30,env={**os.environ,'MPLBACKEND':'Agg'});print(r.returncode,r.stdout[-800:],r.stderr[-800:])
