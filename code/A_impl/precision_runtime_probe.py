import subprocess
for c in [['nvidia-smi'],['bash','-lc','command -v gdb || true'],['/content/luw_wp1_precision/FP32_head/bin/FluidX3D']]:
 p=subprocess.run(c,cwd='/content/luw_wp1_precision/FP32_head',capture_output=True,text=True,timeout=40);print(c,p.returncode,p.stdout[-1200:],p.stderr[-1200:])
