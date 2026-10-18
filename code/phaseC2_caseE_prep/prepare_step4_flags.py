"""Create a separate no-T Case E init-only native flag export (no solver on 工作站)."""
from pathlib import Path
import shutil,tarfile,hashlib
R=Path(__file__).resolve().parent
S=R.parent.parent/'wp1_nearwall/city_stab/stage6_noT'
D=R/'step4_init_stage_v2'
assert not D.exists()
D.mkdir()
shutil.copytree(S/'FluidX3D',D/'FluidX3D',ignore=shutil.ignore_patterns('bin','obj'))
shutil.copytree(S/'case',D/'case',ignore=shutil.ignore_patterns('RESULTS','*.vtk','*.log'))
p=D/'FluidX3D/src/setup.cpp';s=p.read_text()
for old,new in [('Nz<22u','Nz<91u'),('for(uint zf=0u;zf<22u;zf++)','for(uint zf=0u;zf<91u;zf++)'),('native_flags_z0_21.bin','native_flags_z0_90.bin')]:
 assert s.count(old)==1,(old,s.count(old));s=s.replace(old,new)
needle='                ff.flush();if(!ff) print_error("flag export failed");\n            }\n#endif'
assert s.count(needle)==1
s=s.replace(needle,'                ff.flush();if(!ff) print_error("flag export failed");\n            }\n            return; // Flag-only initialization: NO time advancement.\n#endif')
p.write_text(s)
d=D/'FluidX3D/src/defines.hpp';ds=d.read_text();assert ds.count('//#define CITY_STABILITY_MONITOR')==1;d.write_text(ds.replace('//#define CITY_STABILITY_MONITOR','#define CITY_STABILITY_MONITOR'))
tarpath=R/'step4_init_stage_v2.tar.gz'
assert not tarpath.exists()
with tarfile.open(tarpath,'w:gz') as t:
 t.add(D/'FluidX3D',arcname='FluidX3D');t.add(D/'case',arcname='case')
print(tarpath,tarpath.stat().st_size,hashlib.sha256(tarpath.read_bytes()).hexdigest())
