import os,subprocess,traceback,pathlib
try:
 env={**os.environ,'MPLBACKEND':'Agg','OPENBLAS_NUM_THREADS':'1','NUMBA_NUM_THREADS':'1'}
 for cmd in (['uv','pip','install','--python','/content/diagvenv3/bin/python','pyarrow==19.0.1'], ['/content/diagvenv3/bin/python','-u','/content/diag_inputs.py','--out','/content/diagout']):
  print('CMD',cmd,flush=True)
  p=subprocess.Popen(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
  for line in p.stdout:print(line,end='',flush=True)
  code=p.wait()
  if code:raise RuntimeError('exit '+str(code)+' command '+str(cmd))
 pathlib.Path('/content/diag_run.done').write_text('success\n')
except Exception:
 traceback.print_exc();pathlib.Path('/content/diag_run.failed_v5').write_text(traceback.format_exc())
