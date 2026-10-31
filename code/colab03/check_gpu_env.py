import os,subprocess
print('CUDA_VISIBLE_DEVICES',repr(os.getenv('CUDA_VISIBLE_DEVICES')))
print('NVIDIA_VISIBLE_DEVICES',repr(os.getenv('NVIDIA_VISIBLE_DEVICES')))
r=subprocess.run(['nvidia-smi','-L'],capture_output=True,text=True);print('SMI',r.returncode,r.stdout[-500:],r.stderr[-500:])
for pid in (23689,23690,23691):
 try:
  raw=open(f'/proc/{pid}/environ','rb').read().split(b'\0');print(pid,[x.decode(errors='replace') for x in raw if x.startswith((b'CUDA_VISIBLE_DEVICES=',b'NVIDIA_VISIBLE_DEVICES=',b'LD_LIBRARY_PATH='))])
 except OSError:pass
