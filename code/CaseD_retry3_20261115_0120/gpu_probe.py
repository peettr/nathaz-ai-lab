import subprocess
p=subprocess.run(['nvidia-smi','--query-gpu=name,memory.total','--format=csv,noheader,nounits'],capture_output=True,text=True)
print('GPU',repr(p.stdout),p.returncode,flush=True)
assert p.returncode==0 and 'A100' in p.stdout and int(p.stdout.split(',')[-1].strip())>=79000,'80GB A100 required'
