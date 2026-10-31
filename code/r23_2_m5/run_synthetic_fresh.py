import subprocess
r=subprocess.run(['python3','/content/m5/test_m5_main_synthetic.py'],capture_output=True,text=True,timeout=150)
print('RETURN',r.returncode,'STDOUT',r.stdout[-2000:],'STDERR',r.stderr[-3000:])
assert r.returncode==0
