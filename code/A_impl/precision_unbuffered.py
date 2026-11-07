import subprocess
p=subprocess.run(['stdbuf','-o0','-e0','/content/luw_wp1_precision/FP32_head/bin/FluidX3D'],cwd='/content/luw_wp1_precision/FP32_head',capture_output=True,text=True,timeout=45)
print('RC',p.returncode,'OUT',p.stdout[-6000:],'ERR',p.stderr[-6000:])
