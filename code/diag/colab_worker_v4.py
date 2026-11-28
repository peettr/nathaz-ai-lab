import os,subprocess,traceback,pathlib
try:
 env={**os.environ,'MPLBACKEND':'Agg','OPENBLAS_NUM_THREADS':'1','NUMBA_NUM_THREADS':'1'}
 p=subprocess.Popen(['/content/diagvenv3/bin/python','-u','/content/diag_inputs.py','--out','/content/diagout'],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 for line in p.stdout: print(line,end='',flush=True)
 code=p.wait()
 if code: raise RuntimeError('diagnostic exit '+str(code))
 pathlib.Path('/content/diag_run.done').write_text('success\n')
except Exception:
 traceback.print_exc()
 pathlib.Path('/content/diag_run.failed_v4').write_text(traceback.format_exc())
