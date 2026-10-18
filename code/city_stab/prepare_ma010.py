"""Stage a single-factor lower-lattice-speed Case E run; no local solver."""
from pathlib import Path
import shutil, tarfile, hashlib
root=Path(__file__).resolve().parent
src=root/'stage4_nan'; dst=root/'stage5_ma010'
assert not dst.exists(), 'preserve previous stage/result'
shutil.copytree(src,dst,ignore=shutil.ignore_patterns('bin','obj','RESULTS','*.vtk','*.log'))
p=dst/'FluidX3D/src/setup.cpp'; s=p.read_text()
assert s.count('const float lbm_ref_u = 0.10f;')==1
s=s.replace('const float lbm_ref_u = 0.10f;', 'const float lbm_ref_u = 0.06f; // Ma~0.104, single-factor speed ablation')
assert 'for(uint zf=0u;zf<22u;zf++)' in s
s=s.replace('for(uint zf=0u;zf<22u;zf++)','for(uint zf=0u;zf<63u;zf++)')
s=s.replace('Nz<22u) print_error("stage3 flag export grid mismatch")','Nz<63u) print_error("stage5 flag export grid mismatch")')
s=s.replace('native_flags_z0_21.bin','native_flags_z0_62.bin')
p.write_text(s)
p=dst/'case/conf.luwpf'; s=p.read_text()
for old,new in [('run_nstep = 31000','run_nstep = 51667'),('purge_avg = 20000','purge_avg = 33333'),('purge_avg_stride = 40','purge_avg_stride = 67')]:
 assert s.count(old)==1, old
 s=s.replace(old,new)
p.write_text(s)
assert hashlib.sha256((dst/'case/wind_bc/profile.dat').read_bytes()).hexdigest()=='4fc0eede9c5e62bff57127ba176591da4fc7e30723ae51eaddacabb8b41c05fa'
archive=root/'city_ma010_inputs.tar.gz';assert not archive.exists()
with tarfile.open(archive,'w:gz') as t:
 t.add(dst/'FluidX3D',arcname='FluidX3D');t.add(dst/'case',arcname='case')
print(archive,archive.stat().st_size,hashlib.sha256(archive.read_bytes()).hexdigest())
