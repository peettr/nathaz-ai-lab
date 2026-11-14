import subprocess,sys
cmd=['uv','pip','install','--system','earth2studio==0.19.0','cfgrib','eccodes','s3fs']
p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
print('CMD',cmd,'EXIT',p.returncode,'TAIL',p.stdout[-8000:],flush=True)
if p.returncode: raise RuntimeError('install failed')
