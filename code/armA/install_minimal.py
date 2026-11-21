"""One-shot isolated install, bounded by armA total 11.5 GiB.
Third-party package installation only under the approved armA root.
"""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

root = Path('/groups/kareem/[用户]/L26_22_DIFFLBM_20261114/armA')
venv = root / '.venv2'
limit_mib = 11776

def size():
    p = subprocess.run(['du', '-sm', str(root)], capture_output=True, text=True, check=True)
    value = int(p.stdout.split()[0])
    print(f'ARM_A_MIB={value}', flush=True)
    return value

def run(cmd):
    print('RUN', ' '.join(map(str,cmd)), flush=True)
    p = subprocess.Popen(cmd, cwd=root, start_new_session=True)
    while p.poll() is None:
        if size() > limit_mib:
            print('STOP: armA > 11.5 GiB; terminate installer group', flush=True)
            os.killpg(p.pid, signal.SIGTERM)
            try: p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL); p.wait()
            raise SystemExit(96)
        time.sleep(10)
    if p.returncode:
        raise SystemExit(p.returncode)
    size()

if venv.exists():
    raise SystemExit('Refuse existing .venv2')
if size() > 6500:
    raise SystemExit('Baseline unexpectedly high')
run([sys.executable, '-m', 'venv', str(venv)])
pip = str(venv / 'bin' / 'pip')
run([pip, 'install', '--no-cache-dir', 'jax[cuda12]'])
run([pip, 'install', '--no-cache-dir', '--no-deps', str(root / 'XLB_v0.3.1_src')])
run([pip, 'install', '--no-cache-dir', 'pydantic'])
run([str(venv / 'bin' / 'python'), '-c', 'import jax, xlb, pydantic; print("VERSIONS",jax.__version__,xlb.__version__ if hasattr(xlb,"__version__") else "xlb-import-ok",pydantic.__version__)'])
print('INSTALL_DONE', flush=True)
