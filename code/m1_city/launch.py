import os,subprocess
name=os.environ['RUN_TAG']
with open('/content/m1city_'+name+'_wrapper.log','w') as f:
 p=subprocess.Popen(['python3','/content/remote_run.py'],cwd='/content',env=os.environ.copy(),stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('launched',name,p.pid,flush=True)
