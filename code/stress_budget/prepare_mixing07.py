from pathlib import Path
import shutil,tarfile
b=Path(__file__).resolve().parent;src=b/'stage_mixing';dest=b/'stage_mixing07';assert not dest.exists();shutil.copytree(src,dest)
f=dest/'FluidX3D/src/kernel.cpp';s=f.read_text();needle='const float len=cs_len+taper*fmax(0.0f,def_ground_kappa*z_wall-cs_len);';assert s.count(needle)==1;s=s.replace(needle,'const float len=cs_len+0.70f*taper*fmax(0.0f,def_ground_kappa*z_wall-cs_len);');f.write_text(s)
with tarfile.open(b/'mixing07_inputs.tar.gz','w:gz') as t:
 t.add(dest/'FluidX3D',arcname='FluidX3D');t.add(dest/'case',arcname='case')
print('tuned stage', (b/'mixing07_inputs.tar.gz').stat().st_size)
