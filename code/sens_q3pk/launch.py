from pathlib import Path
import subprocess,sys,os,json
r=Path('/content/sens'); marker=r/'launch.lock'
with marker.open('x') as f:f.write('qc_sens_colab.py\n')
log=(r/'run.log').open('x')
script="import subprocess,pathlib; p=pathlib.Path('/content/sens'); z=subprocess.run([sys.executable,str(p/'qc_sens_colab.py')]); (p/'exit.json').write_text(__import__('json').dumps({'returncode':z.returncode})); sys.exit(z.returncode)"
proc=subprocess.Popen([sys.executable,'-c','import sys; '+script],cwd='/content/sens',stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(r/'pid.json').write_text(json.dumps({'pid':proc.pid}))
print(proc.pid)
