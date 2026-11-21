from pathlib import Path
import subprocess,sys,time,traceback
root=Path('/content/g4_persist')
try:
 with (root/'console.log').open('x') as log:
  p=subprocess.run([sys.executable,str(root/'runner.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,cwd='/content')
  rc=p.returncode
except BaseException:
 (root/'supervisor_error.txt').write_text(traceback.format_exc())
 rc=99
(root/'runner.exit').write_text(str(rc)+' '+str(time.time())+'\n')
