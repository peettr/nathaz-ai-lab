import os,sys,subprocess
from pathlib import Path
P=Path('/content/a3_b_stop_1015');(P/'prior_26.json').write_bytes(Path('/content/prior_26_stop_1015.json').read_bytes())
(P/'.colab_owner').write_text('A3-B stop groups researchos-lab-ideas ideas-a3-bstop-1015')
lock=P/'run_started.lock';lock.open('x').write(str(os.getpid()))
script="import subprocess,sys,time,pathlib\np=pathlib.Path('/content/a3_b_stop_1015');start=time.time()\nwith (p/'run.log').open('w') as f: rc=subprocess.run([sys.executable,'-u','/content/colab_b_stop_run.py'],stdout=f,stderr=subprocess.STDOUT).returncode\n(p/'run.done').write_text(f'{rc} {time.time()-start:.3f}');sys.exit(rc)\n"
(P/'supervisor.py').write_text(script)
with (P/'supervisor.log').open('w') as f:
 child=subprocess.Popen([sys.executable,str(P/'supervisor.py')],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('LAUNCHED',child.pid,flush=True)
