import subprocess
p=subprocess.Popen(["python3","/content/run_stage6_remote.py"],stdin=subprocess.DEVNULL,stdout=open("/content/luw_stage6_driver.log","w"),stderr=subprocess.STDOUT,start_new_session=True)
print("STAGE6_PID",p.pid,flush=True)
