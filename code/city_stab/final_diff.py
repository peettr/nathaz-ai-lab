from pathlib import Path
import difflib,hashlib
R=Path(__file__).resolve().parent
H=Path('./.cache/dwt-luw-eval/core/cfd_core/FluidX3D/src')
S=R/'stage2/FluidX3D/src'
out=[]
for n in ['defines.hpp','kernel.cpp','lbm.cpp','lbm.hpp','setup.cpp']:
 out.extend(difflib.unified_diff((H/n).read_text().splitlines(keepends=True),(S/n).read_text().splitlines(keepends=True),fromfile='a/src/'+n,tofile='b/src/'+n))
p=R/'solver_city_clean_final.diff';assert not p.exists();p.write_text(''.join(out));print(len(out),hashlib.sha256(p.read_bytes()).hexdigest())
