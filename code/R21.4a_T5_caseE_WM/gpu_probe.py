import subprocess,json
q=subprocess.run(['nvidia-smi','--query-gpu=name,memory.total,memory.free','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True).stdout.strip().splitlines()[0]
name,total,free=[x.strip() for x in q.split(',')]
print('GPU',json.dumps({'name':name,'memory_total_mb':int(total),'memory_free_mb':int(free),'max_alloc_mb':int(total)//4}),flush=True)
