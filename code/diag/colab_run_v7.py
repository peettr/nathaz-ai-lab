import subprocess,os
p=subprocess.run(['/content/diagvenv3/bin/python','-u','/content/diag_inputs_v3.py','--out','/content/diagout_v3'],env={**os.environ,'MPLBACKEND':'Agg','OPENBLAS_NUM_THREADS':'1','NUMBA_NUM_THREADS':'1'},stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=125)
print('exit',p.returncode,'\n',p.stdout[-12000:])
