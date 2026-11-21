import os,subprocess
name=os.environ['TAG'];assert name in ('A','B')
f=open('/content/inflow_'+name+'_driver.log','w',buffering=1)
p=subprocess.Popen(['python3','/content/remote_runner.py',name],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('PID',p.pid,flush=True)
