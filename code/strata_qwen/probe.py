import subprocess
for c in ["nvidia-smi --query-gpu=name,memory.total --format=csv","free -g","df -h /content /","nproc","cat /proc/cpuinfo | grep 'model name' | head -1","python -c 'import sys;print(sys.version)'","nvcc --version | tail -1"]:
    print("$",c); print(subprocess.run(c,shell=True,capture_output=True,text=True).stdout, flush=True)
