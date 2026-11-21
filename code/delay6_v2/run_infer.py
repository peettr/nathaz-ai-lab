import subprocess,sys,time
from pathlib import Path
r=Path('/content/delay6');start=time.time()
with (r/'infer.log').open('x') as f:
    p=subprocess.run([sys.executable,'-u',str(r/'infer.py')],stdout=f,stderr=subprocess.STDOUT)
(r/'infer.exit').write_text(str(p.returncode)+'\n')
(r/'infer.wall').write_text(str(time.time()-start)+'\n')
print('INFER_EXIT',p.returncode,flush=True)
