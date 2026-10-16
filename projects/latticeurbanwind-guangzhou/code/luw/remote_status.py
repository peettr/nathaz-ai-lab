from pathlib import Path
import subprocess,time
r=Path('/content/luw-aij'); repo=r/'repo'
for name in ['install','compile']:
 p=r/(name+'.log'); s=p.read_text(errors='replace') if p.exists() else ''; print(name,'size',len(s),'TAIL',s[-2400:],flush=True)
print('venv', (repo/'.venv/bin/python').exists(),'binary',(repo/'core/cfd_core/FluidX3D/bin/FluidX3D').exists())
print('processes',subprocess.run(['ps','-eo','pid,etime,rss,args'],capture_output=True,text=True).stdout[-3500:])
