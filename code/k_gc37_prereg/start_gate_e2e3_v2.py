import os, pathlib, subprocess
root=pathlib.Path('/content/r234c_gc37_E2E3')
root.mkdir(exist_ok=True)
assert not (root/'numeric_gate_worker.exit.json').exists()
log=(root/'numeric_gate_worker_v2.log').open('x')
p=subprocess.Popen(['python3','-u','/content/launch_numeric_gate_e2e3_25cu_v2.py'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,cwd='/content')
print('GATE_PID',p.pid,'LOG',log.name)
