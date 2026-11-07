import os,subprocess,sys,time
model=os.environ.get('R2_MODEL','30b'); start=time.monotonic()
with open('/content/local_'+model+'_run_r2.log','w',buffering=1) as f:
 p=subprocess.run([sys.executable,'/content/run_local_r2.py'],stdout=f,stderr=subprocess.STDOUT,env=os.environ.copy())
print('SUBPROCESS EXIT',p.returncode,'ELAPSED',round(time.monotonic()-start,1),'LOG','/content/local_'+model+'_run_r2.log',flush=True)
assert p.returncode==0
