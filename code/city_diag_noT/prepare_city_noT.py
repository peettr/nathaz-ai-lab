"""Stage three isolated Case E configurations; never run solver locally."""
from pathlib import Path
import shutil,tarfile,hashlib,json
R=Path(__file__).resolve().parent
S=R.parent/'city_stab/stage6_noT'
A=R/'stage'
assert not A.exists()
shutil.copytree(S,A,ignore=shutil.ignore_patterns('bin','obj','RESULTS','*.vtk','*.log'))
p=A/'FluidX3D/src/defines.hpp'
s=p.read_text(); old='//#define GROUND_WALL_MODEL'; assert s.count(old)==1
s=s.replace(old,'#define GROUND_WALL_MODEL');p.write_text(s)
for name in ('profile.dat','conf.luwpf'):
 path=A/'case'/('wind_bc' if name=='profile.dat' else '')/name
 print(name,hashlib.sha256(path.read_bytes()).hexdigest())
for name in ('defines.hpp','setup.cpp','kernel.cpp'):
 path=A/'FluidX3D/src'/name
 print(name,hashlib.sha256(path.read_bytes()).hexdigest())
assert '#define TEMPERATURE' not in [line.strip() for line in s.splitlines()]
assert '#define GROUND_WALL_MODEL' in s
assert 'def_ground_mix_a*taper' in (A/'FluidX3D/src/kernel.cpp').read_text()
archive=R/'city_diag_noT_inputs.tar.gz'
assert not archive.exists()
with tarfile.open(archive,'w:gz') as t:
 t.add(A/'FluidX3D',arcname='FluidX3D');t.add(A/'case',arcname='case')
print('archive',archive.stat().st_size,hashlib.sha256(archive.read_bytes()).hexdigest())
