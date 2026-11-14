from pathlib import Path
import tarfile,hashlib
R=Path(__file__).resolve().parent
H=Path('./.cache/dwt-luw-eval/core/cfd_core/FluidX3D')
with tarfile.open(R/'city_head_inputs.tar.gz','w:gz') as t:
 t.add(H,arcname='FluidX3D',filter=lambda info: None if any(k in info.name for k in ('/bin/','/obj/','/.git/')) else info)
 t.add(R/'stage2/case',arcname='case')
print(hashlib.sha256((R/'city_head_inputs.tar.gz').read_bytes()).hexdigest())
