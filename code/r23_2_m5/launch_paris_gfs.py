from pathlib import Path
import subprocess,sys,os
r=Path('/content/m5')
(r/'paris_gfs.launch').open('x').write('one launch\n')
worker="import subprocess; from pathlib import Path; r=Path('/content/m5'); p=subprocess.run(['python3',str(r/'m5_paris_gfs.py')]); (r/'paris_gfs.exit').write_text(str(p.returncode)+'\\n'); (r/'paris_gfs.done').touch()"
with (r/'paris_gfs.log').open('w') as log:
    p=subprocess.Popen([sys.executable,'-c',worker],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,cwd=str(r))
print('LAUNCHED_PARIS_GFS',p.pid,flush=True)
