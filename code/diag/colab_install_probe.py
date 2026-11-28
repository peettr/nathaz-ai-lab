import subprocess,sys
p=subprocess.run([sys.executable,'-m','pip','install','climada==6.1.0'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
print('exit',p.returncode,'\n',p.stdout[-8000:],flush=True)
