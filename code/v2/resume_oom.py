"""Resume once after verified original OOM process group exited."""
import os
import subprocess
from pathlib import Path
p=Path('/content/l26v2')
assert (p/'oom_recovery.lock').exists()
assert not (p/'run.done').exists()
assert not (p/'answers_A.jsonl').exists()
procs=subprocess.run(['ps','-eo','args'],capture_output=True,text=True).stdout
assert '/content/l26v2/run.py' not in procs and 'VLLM::EngineCore' not in procs
assert 'language_model_only=True' in (p/'run.py').read_text()
fd=os.open(p/'oom_resume.lock',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o644)
os.write(fd,b'one text-only recovery\n');os.close(fd)
with (p/'run.log').open('a') as log:
    log.write('\nRECOVERY after multimodal profiler OOM: text-only, max_num_seqs=1\n')
    log.flush()
    proc=subprocess.Popen(['python3',str(p/'run.py')],stdin=subprocess.DEVNULL,
        stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('recovery pid',proc.pid)
