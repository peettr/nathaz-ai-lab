import subprocess,pathlib
pathlib.Path('/content/diag_run.launch_v6').open('x').write('endpoint carry diagnostic, new immutable output\n')
f=open('/content/diag_run_v6.log','x')
q=subprocess.Popen(['/content/diagvenv3/bin/python','-u','/content/diag_inputs_v2.py','--out','/content/diagout_v2'],env={'PATH':'/usr/bin:/bin','HOME':'/root','MPLBACKEND':'Agg','OPENBLAS_NUM_THREADS':'1','NUMBA_NUM_THREADS':'1'},stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,cwd='/content')
print('pid',q.pid)
