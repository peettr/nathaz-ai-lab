import subprocess, json, os, platform, time
for label, cmd in [('gpu',['nvidia-smi','--query-gpu=name,memory.total,compute_cap','--format=csv,noheader']),('memory',['free','-h']),('disk',['df','-h','/content']),('cuda',['nvcc','--version']),('cpu',['nproc'])]:
 try:
  p=subprocess.run(cmd,capture_output=True,text=True,timeout=15)
  print(label,p.returncode,p.stdout.strip(),p.stderr.strip(),flush=True)
 except Exception as e: print(label,'error',str(e),flush=True)
print('python',platform.python_version(),flush=True)
