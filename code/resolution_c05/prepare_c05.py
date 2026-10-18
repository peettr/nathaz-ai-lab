"""Build a fresh C05 stage from read-only C1v2; do not run solver locally."""
from pathlib import Path
import shutil,hashlib,json,tarfile
R=Path(__file__).resolve().parent
SRC=R.parent/'resolution_crop_v2/stage_C1v2'
OUT=R/'stage_C05'
assert not OUT.exists()
shutil.copytree(SRC,OUT,ignore=shutil.ignore_patterns('bin','obj','RESULTS','*.vtk','*.log'))
conf=OUT/'case/conf.luwpf';s=conf.read_text()
for a,b in [('cell_size = 1.0','cell_size = 0.5'),('purge_avg = 20000','purge_avg = 40000'),('run_nstep = 31000','run_nstep = 62000'),('purge_avg_stride = 40','purge_avg_stride = 80')]:
 assert s.count(a)==1,(a,s.count(a));s=s.replace(a,b)
conf.write_text(s)
setup=OUT/'FluidX3D/src/setup.cpp';t=setup.read_text()
assert 'const float z_agl = std::max(0.0f,(p.z - 20.0f/cfg_.cell_size_m) * cfg_.cell_size_m);' in t
# Keep the physical ground 20 m datum; replace opaque literal with explicit expression.
t=t.replace('const float z_agl = std::max(0.0f,(p.z - 20.0f/cfg_.cell_size_m) * cfg_.cell_size_m);','const float ground_z_m = 20.0f; // same physical datum as C1v2\n                const float z_agl = std::max(0.0f, p.z*cfg_.cell_size_m - ground_z_m);')
setup.write_text(t)
files=['case/wind_bc/profile.dat','case/proj_temp/CaseE_PF.stl','case/conf.luwpf','FluidX3D/src/setup.cpp']
manifest={x:hashlib.sha256((OUT/x).read_bytes()).hexdigest() for x in files}
assert manifest[files[0]]==hashlib.sha256((SRC/files[0]).read_bytes()).hexdigest()
assert manifest[files[1]]==hashlib.sha256((SRC/files[1]).read_bytes()).hexdigest()
(R/'C05_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
with tarfile.open(R/'C05_inputs.tar.gz','w:gz') as tar:
 tar.add(OUT/'FluidX3D',arcname='FluidX3D');tar.add(OUT/'case',arcname='case')
print(json.dumps(manifest,indent=2))
