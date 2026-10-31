import subprocess,os,sys,requests,tarfile,io
from pathlib import Path
r=Path('/content/e_terrain')
u='https://micro.mamba.pm/api/micromamba/linux-64/latest'
print('fetch',u,flush=True)
b=requests.get(u,timeout=120);b.raise_for_status()
with tarfile.open(fileobj=io.BytesIO(b.content),mode='r:bz2') as t:
 obj=t.extractfile('bin/micromamba');exe=r/'micromamba';exe.write_bytes(obj.read());exe.chmod(0o755)
print('micromamba size',exe.stat().st_size,flush=True)
cmd=[str(exe),'create','-y','-p',str(r/'wn_env'),'-c','conda-forge','windninja']
print('start',cmd,flush=True)
p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=1500,env={**os.environ,'MAMBA_ROOT_PREFIX':str(r/'mamba')})
(r/'wn_install.log').write_text(p.stdout)
print('INSTALL_RC',p.returncode,'TAIL',p.stdout[-2500:],flush=True)
