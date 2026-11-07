"""FP32 first-layer city control, identical staged source except a=0."""
from pathlib import Path
import shutil,tarfile,hashlib
R=Path(__file__).resolve().parent
s=R/'stage_mix07';d=R/'stage_mix00';assert s.exists() and not d.exists()
shutil.copytree(s,d)
p=d/'FluidX3D/src/kernel.cpp';v=p.read_text();old='0.70f*taper*fmax(0.0f,def_ground_kappa*z_wall-cs_len)';assert v.count(old)==1;p.write_text(v.replace(old,'0.0f*taper*fmax(0.0f,def_ground_kappa*z_wall-cs_len)'))
tar=R/'mix00_inputs.tar.gz'
with tarfile.open(tar,'w:gz') as t:t.add(d/'FluidX3D',arcname='FluidX3D');t.add(d/'case',arcname='case')
print(tar.stat().st_size,hashlib.sha256(tar.read_bytes()).hexdigest())
