import subprocess
p=subprocess.Popen(['python3','/content/remote_runner_v2.py','B2'],stdin=subprocess.DEVNULL,stdout=open('/content/inflow_B2_driver.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print(p.pid)
