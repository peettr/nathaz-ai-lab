from pathlib import Path
import difflib,tarfile,hashlib
R=Path(__file__).resolve().parent
H=Path('./.cache/dwt-luw-eval/core/cfd_core/FluidX3D/src')
S=R/'stage2/FluidX3D/src'
changes=[]
for n in ['defines.hpp','kernel.cpp','lbm.cpp','lbm.hpp','setup.cpp']:
 changes.extend(difflib.unified_diff((H/n).read_text().splitlines(keepends=True),(S/n).read_text().splitlines(keepends=True),fromfile='a/src/'+n,tofile='b/src/'+n))
(R/'solver_city_clean.diff').write_text(''.join(changes))
with tarfile.open(R/'city_clean_inputs.tar.gz','w:gz') as t:
 t.add(R/'stage2/FluidX3D',arcname='FluidX3D')
 t.add(R/'stage2/case',arcname='case')
print(hashlib.sha256((R/'city_clean_inputs.tar.gz').read_bytes()).hexdigest())
