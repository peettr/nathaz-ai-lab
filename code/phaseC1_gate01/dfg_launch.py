import subprocess,os
p=subprocess.Popen(['python3','-u','/content/dfg_full_driver.py'],stdin=subprocess.DEVNULL,stdout=open('/content/dfg_full_progress.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('DFG_PID',p.pid,flush=True)
