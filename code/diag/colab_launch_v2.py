import subprocess,pathlib
pathlib.Path('/content/diag_run.launch_v2').open('x').write('retry dependency gdal 3.8.4\n')
f=open('/content/diag_run.log','a')
q=subprocess.Popen(['/usr/bin/python3','/content/colab_worker_v2.py'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,cwd='/content')
print('pid',q.pid)
