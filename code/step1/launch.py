import subprocess
subprocess.Popen("nohup python /content/run_gate.py > /content/run.log 2>&1 &", shell=True)
print("launched", flush=True)
