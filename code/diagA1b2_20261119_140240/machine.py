import json,subprocess
try:
    p=subprocess.run(['nvidia-smi','--query-gpu=name,memory.total,memory.free','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=12)
    gpu=dict(rc=p.returncode,stdout=p.stdout,stderr=p.stderr)
except (OSError,subprocess.TimeoutExpired) as e:
    gpu=dict(rc=None,stdout='',stderr=str(e))
print('GPU_MACHINE '+json.dumps(gpu),flush=True)
print(next(x.strip() for x in open('/proc/meminfo') if x.startswith('MemAvailable:')))
