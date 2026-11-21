import subprocess
subprocess.run(['nvidia-smi','--query-gpu=name,memory.total,memory.free','--format=csv,noheader,nounits'],check=True)
print(next(x.strip() for x in open('/proc/meminfo') if x.startswith('MemAvailable:')))
