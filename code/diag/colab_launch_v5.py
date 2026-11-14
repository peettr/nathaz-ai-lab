import subprocess,pathlib
pathlib.Path('/content/diag_run.launch_v5').open('x').write('pin pyarrow 19 for numpy 1.26\n')
f=open('/content/diag_run.log','a')
q=subprocess.Popen(['/usr/bin/python3','/content/colab_worker_v5.py'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,cwd='/content')
print('pid',q.pid)
