import subprocess
print(subprocess.run(["pgrep","-af","run_stage6_remote"],capture_output=True,text=True).stdout)
print(subprocess.run(["pgrep","-af","FluidX3D"],capture_output=True,text=True).stdout)