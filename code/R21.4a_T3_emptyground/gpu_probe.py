import subprocess,os,time
print('GPU',subprocess.run(['nvidia-smi','--query-gpu=name,memory.total,memory.free','--format=csv,noheader,nounits'],capture_output=True,text=True).stdout.strip())
print('HOST_AVAILABLE_KB',next(x.strip() for x in open('/proc/meminfo') if x.startswith('MemAvailable:')))
print('TIME',time.time())
