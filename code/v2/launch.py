import os, subprocess, sys
from pathlib import Path
root=Path('/content/l26v2')
root.mkdir(exist_ok=True)
lock=root/'launch.lock'
fd=os.open(str(lock),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o644)
os.write(fd,b'one launch only\n');os.close(fd)
script='''#!/bin/bash
set -e
python -m pip install -q --upgrade 'vllm>=0.14' 'transformers>=5.0' huggingface_hub
python /content/l26v2/run.py
'''
p=root/'start.sh';p.write_text(script);p.chmod(0o755)
with (root/'run.log').open('w') as log:
    proc=subprocess.Popen(['nohup','bash',str(p)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('launched pid',proc.pid, 'log',str(root/'run.log'))
