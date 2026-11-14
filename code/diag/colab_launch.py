import subprocess, pathlib, os
p=pathlib.Path('/content/diag_run.launch');p.open('x').write('started\n')
f=open('/content/diag_run.log','x')
q=subprocess.Popen(['/usr/bin/python3','/content/colab_worker.py'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,cwd='/content')
print('pid',q.pid)
