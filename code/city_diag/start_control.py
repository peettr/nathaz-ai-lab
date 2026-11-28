import subprocess
p=subprocess.Popen(['python3','/content/run_control.py'],stdout=open('/content/control_job.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('CONTROL_PID',p.pid,flush=True)
