import subprocess
p=subprocess.run(['uv','pip','install','--python','/content/hrrr_env/bin/python','tensorflow[and-cuda]==2.15.0'],capture_output=True,text=True,timeout=500)
print('EXIT',p.returncode,'OUT',p.stdout[-1000:],'ERR',p.stderr[-1500:],flush=True)
