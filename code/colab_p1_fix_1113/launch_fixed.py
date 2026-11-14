# Start a single detached supervisor: smoke, gate, then full batch.
import os, subprocess
from pathlib import Path
assert not Path('/content/a170_2').exists()
assert not Path('/content/a170_2_campaign.done').exists()
e=os.environ.copy()
e.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
with Path('/content/a170_2_supervisor.log').open('w') as f:
 p=subprocess.Popen(['python3','-u','/content/supervisor_fixed.py'],cwd='/content',env=e,
                    stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('SUPERVISOR_PID',p.pid)
