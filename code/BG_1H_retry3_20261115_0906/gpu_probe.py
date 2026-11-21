import subprocess
p=subprocess.run(['nvidia-smi','--query-gpu=name,memory.total,memory.free','--format=csv,noheader,nounits'],capture_output=True,text=True)
mem=subprocess.run(['free','-g'],capture_output=True,text=True)
print('NVIDIA_SMI',p.stdout.strip(),'FREE_G',mem.stdout.strip(),flush=True)
assert p.returncode==0 and mem.returncode==0
name,total,free=[v.strip() for v in p.stdout.strip().splitlines()[0].split(',')]
avail_kib=int(next(l.split()[1] for l in open('/proc/meminfo') if l.startswith('MemAvailable:')))
print('MEMCHECK','GPU_NAME',name,'GPU_TOTAL_MIB',total,'GPU_FREE_MIB',free,'HOST_AVAILABLE_KIB',avail_kib,'REQUIRE_GPU_MIB',15360,'REQUIRE_HOST_KIB',10*1024*1024,flush=True)
assert int(total)>=23000 and int(free)>=15360 and avail_kib>=10*1024*1024,'BG_1H estimated peak memory exceeds available memory; stop before transfer/build/solver'
