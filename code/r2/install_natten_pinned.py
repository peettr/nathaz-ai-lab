import subprocess
p=subprocess.run(['pip','install','-q','natten==0.21.6+torch2110cu130','-f','https://whl.natten.org'],capture_output=True,text=True,timeout=220)
print('NATTEN_PINNED',p.returncode,p.stdout[-500:],p.stderr[-1500:],flush=True)
