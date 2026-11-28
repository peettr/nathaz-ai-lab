"""One-shot autonomous handoff: no continuation until existing phase1 completes."""
import os, subprocess, time, pathlib, sys
root=pathlib.Path('/content')
claim=root/'a170_4_cont.launch'
with claim.open('x') as f: f.write(str(os.getpid()))
while not (root/'a170_4_phase1.done').exists():
    if (root/'a170_4_phase1.failed').exists():
        print('PHASE1_FAILED_NO_CONTINUATION',flush=True);sys.exit(2)
    time.sleep(10)
print('PHASE1_DONE_START_CONT',flush=True)
p=subprocess.run([sys.executable,'-u',str(root/'worker_a170_4_cont.py')],stdin=subprocess.DEVNULL)
print('CONT_EXIT',p.returncode,flush=True)
sys.exit(p.returncode)
