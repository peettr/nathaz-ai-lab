from pathlib import Path
import subprocess, sys
root=Path('/content/l2631')
assert (root/'weatherbench/stage.done').exists(), 'staging incomplete'
assert not (root/'train.start').exists(), 'training already started'
(root/'train.start').open('x').write('D1b A0 early stop 3 seeds\n')
runner=root/'run_train_wrapper.py'
assert runner.exists()
log=(root/'train.log').open('xb')
p=subprocess.Popen([sys.executable,'-u',str(runner)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('TRAIN_STARTED',p.pid)
