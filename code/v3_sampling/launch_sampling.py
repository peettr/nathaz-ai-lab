from pathlib import Path
import subprocess
p=Path('/content/sampling.launch')
with p.open('x') as f:f.write('R23.3a-05\n')
cmd="python -u /content/sampling_worker.py > /content/sampling.log 2>&1; code=$?; echo $code > /content/sampling.exit; touch /content/sampling.done"
proc=subprocess.Popen(['bash','-c',cmd],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print('worker_pid',proc.pid)
