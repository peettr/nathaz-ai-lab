"""One-time recovery in owned VM after vLLM multimodal profiler OOM."""
import os
import signal
import subprocess
import time
from pathlib import Path
p=Path('/content/l26v2')
assert not (p/'run.done').exists()
assert not (p/'answers_A.jsonl').exists(), 'Do not restart without checking existing answers'
marker=p/'oom_recovery.lock'
fd=os.open(marker, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o644)
os.write(fd,b'one recovery after multimodal profile OOM\n');os.close(fd)
old=671
cmd=Path(f'/proc/{old}/cmdline')
if cmd.exists():
    assert b'/content/l26v2/start.sh' in cmd.read_bytes()
    os.killpg(old,signal.SIGTERM)
    print('Terminated old launcher process group',old,flush=True)
for _ in range(30):
    procs=subprocess.run(['ps','-eo','args'],capture_output=True,text=True).stdout
    if '/content/l26v2/run.py' not in procs and 'VLLM::EngineCore' not in procs:
        break
    time.sleep(2)
else:
    raise RuntimeError('Old engine still alive, refusing duplicate launch')
assert 'language_model_only=True' in (p/'run.py').read_text()
with (p/'run.log').open('a') as log:
    log.write('\nRECOVERY: text-only vLLM, max_num_seqs=1; prior multimodal profiler OOM\n')
    log.flush()
    proc=subprocess.Popen(['python3',str(p/'run.py')],stdin=subprocess.DEVNULL,
        stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('recovery pid',proc.pid,flush=True)
