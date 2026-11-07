import subprocess
p=subprocess.Popen(['python3','/content/run_H2_trial.py'],stdin=subprocess.DEVNULL,stdout=open('/content/luw_c3_H2_driver.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('H2_PID',p.pid,flush=True)
