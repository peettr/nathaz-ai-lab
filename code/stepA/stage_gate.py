"""Install isolated VM dependencies and execute the post-merge gate."""
import subprocess,sys,traceback
from pathlib import Path
R=Path('/content/l2612-stepA');R.mkdir(exist_ok=True)
try:
 subprocess.run([sys.executable,'-m','pip','install','-q','onnx','onnxruntime-gpu','xarray','zarr<3','gcsfs'],check=True)
 print('install_done',flush=True)
 subprocess.run([sys.executable,'/content/gate_stepA.py'],check=True)
 print('gate_done',flush=True)
except BaseException:
 traceback.print_exc();(R/'gate.done').write_text('error')
