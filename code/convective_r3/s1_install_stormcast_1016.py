import subprocess,sys
for cmd in [['uv','pip','install','--system','earth2studio[stormcast]==0.19.0'],['uv','pip','install','--system','natten==0.21.6+torch2110cu130','--find-links','https://whl.natten.org']]:
 p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=420)
 print('CMD',cmd,'EXIT',p.returncode,'TAIL',p.stdout[-4000:],flush=True)
 if p.returncode:break
