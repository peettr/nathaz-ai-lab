# Start one Colab CPU smoke process without blocking the kernel.
import os,subprocess
from pathlib import Path
assert not Path('/content/a170_2').exists()
p=Path('/content/a170_2_smoke.log').open('w')
e=os.environ.copy();e.update(P1_SHA256='e55cf7ea02fa5fda56bf276883fb874ac2ac4145c9a4d5cf1f70d25d06f877fb',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
job=subprocess.Popen(['python3','-u','/content/colab_a170_2.py','smoke'],cwd='/content',env=e,stdout=p,stderr=subprocess.STDOUT,start_new_session=True)
print('SMOKE_PID',job.pid)
