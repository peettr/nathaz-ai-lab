"""Correct isolated monitor omission in ma010 attempt 1."""
from pathlib import Path
import shutil,tarfile,hashlib
r=Path(__file__).resolve().parent
src=r/'stage5_ma010';dst=r/'stage5b_ma010'
assert not dst.exists()
shutil.copytree(src,dst,ignore=shutil.ignore_patterns('bin','obj','RESULTS','*.vtk','*.log'))
p=dst/'FluidX3D/src/defines.hpp';s=p.read_text();assert s.count('//#define CITY_STABILITY_MONITOR')==1;s=s.replace('//#define CITY_STABILITY_MONITOR','#define CITY_STABILITY_MONITOR');p.write_text(s)
a=r/'city_ma010_inputs_v2.tar.gz';assert not a.exists()
with tarfile.open(a,'w:gz') as t:
 t.add(dst/'FluidX3D',arcname='FluidX3D');t.add(dst/'case',arcname='case')
print(a,a.stat().st_size,hashlib.sha256(a.read_bytes()).hexdigest())
