import subprocess
p=subprocess.run(['pip','install','-q','earth2studio[stormcast]==0.19.0'],capture_output=True,text=True,timeout=400)
print('INSTALL_EXIT',p.returncode,p.stdout[-1000:],p.stderr[-3000:],flush=True)
