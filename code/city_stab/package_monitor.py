from pathlib import Path
import tarfile,hashlib
R=Path(__file__).resolve().parent
with tarfile.open(R/'city_monitor_inputs.tar.gz','w:gz') as t:
 t.add(R/'stage2/FluidX3D',arcname='FluidX3D');t.add(R/'stage2/case',arcname='case')
print(hashlib.sha256((R/'city_monitor_inputs.tar.gz').read_bytes()).hexdigest())
