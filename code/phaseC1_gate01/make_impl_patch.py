from pathlib import Path
import difflib
root=Path(__file__).parent
src=Path('./.cache/dwt-luw-eval/core/cfd_core/FluidX3D/src')
dst=root/'impl_stage/FluidX3D/src'
files=['defines.hpp','kernel.cpp','lbm.cpp','lbm.hpp','setup.cpp','ibb_fixture.inc']
chunks=[]
for name in files:
 old=(src/name).read_text().splitlines(keepends=True) if (src/name).exists() else []
 new=(dst/name).read_text().splitlines(keepends=True)
 path='core/cfd_core/FluidX3D/src/'+name
 if old==new:continue
 chunks.extend(difflib.unified_diff(old,new,fromfile='a/'+path if old else '/dev/null',tofile='b/'+path))
out=root/'solver_LINK_IBB_against_dd438c1.patch'
out.write_text(''.join(chunks))
print(out,len(chunks),out.stat().st_size)
