"""Prepare immutable new cont5 inputs from cont4 archive and current solver."""
from pathlib import Path
import tarfile,tempfile,shutil
r=Path(__file__).resolve().parent
old=r/'empty_cont4_inputs.tar.gz';new=r/'empty_cont5b_inputs.tar.gz'
assert old.exists() and not new.exists()
with tempfile.TemporaryDirectory(dir=r) as d:
 d=Path(d)
 with tarfile.open(old) as t:t.extractall(d,filter='data')
 src=r/'LatticeUrbanWind_repo/core/cfd_core/FluidX3D/src'
 for name in ('defines.hpp','kernel.cpp','lbm.cpp','lbm.hpp','setup.cpp'):
  shutil.copy2(src/name,d/'FluidX3D/src'/name)
 with tarfile.open(new,'w:gz') as t:
  for child in d.iterdir():t.add(child,arcname=child.name)
print(new,new.stat().st_size)
