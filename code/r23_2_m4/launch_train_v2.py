"""Launch the immutable training-only first stage once on Colab."""
import os, subprocess, sys
from pathlib import Path
root=Path('/content/m4');root.mkdir(exist_ok=True)
marker=root/'train_v2.launch'
with marker.open('x') as f:f.write('training only; no holdout reads\n')
script="""#!/bin/bash
set -o pipefail
cd /content
python3 /content/m4_training.py obs && python3 /content/m4_training.py gfs && python3 /content/m4_training.py fit
rc=$?
printf '%s\\n' "$rc" > /content/m4/train_v2.exit
if [ "$rc" -eq 0 ]; then touch /content/m4/train_v2.done; fi
exit "$rc"
"""
runner=root/'run_train_v2.sh';runner.write_text(script);runner.chmod(0o755)
log=open(root/'train_v2.log','x')
p=subprocess.Popen(['/bin/bash',str(runner)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('TRAIN_PID',p.pid,'LOG',log.name,'MARKER',marker)
