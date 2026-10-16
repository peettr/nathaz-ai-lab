import subprocess
p=subprocess.run(['pip','install','-q','nvidia-physicsnemo[natten-cu12]'],capture_output=True,text=True,timeout=250)
print('NATTEN_INSTALL_EXIT',p.returncode,'OUT',p.stdout[-500:],'ERR',p.stderr[-2500:],flush=True)
