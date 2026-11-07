from pathlib import Path
import shutil,tarfile,hashlib,json
R=Path(__file__).resolve().parent
base=R.parent/'approach_full/stage_FG0A70'
wale=R/'stage_floor_E1'
for tag,ground in [('FW',False),('FG0W',True)]:
 d=R/('stage_'+tag); assert not d.exists()
 shutil.copytree(base,d,ignore=shutil.ignore_patterns('bin','obj','RESULTS','*.vtk','*.log'))
 for name in ('defines.hpp','kernel.cpp','lbm.cpp','lbm.hpp'):
  shutil.copy2(wale/'FluidX3D/src'/name,d/'FluidX3D/src'/name)
 if ground:
  p=d/'FluidX3D/src/defines.hpp';s=p.read_text();old='//#define GROUND_WALL_MODEL // experimental';assert s.count(old)==1;p.write_text(s.replace(old,'#define GROUND_WALL_MODEL // experimental'))
 files=['case/wind_bc/profile.dat','case/proj_temp/CaseE_PF.stl','case/conf.luwpf','FluidX3D/src/setup.cpp','FluidX3D/src/defines.hpp','FluidX3D/src/kernel.cpp','FluidX3D/src/lbm.cpp','FluidX3D/src/lbm.hpp']
 (R/(tag+'_manifest.json')).write_text(json.dumps({f:hashlib.sha256((d/f).read_bytes()).hexdigest() for f in files},indent=2)+'\n')
 with tarfile.open(R/(tag+'_inputs.tar.gz'),'w:gz') as t:t.add(d/'FluidX3D',arcname='FluidX3D');t.add(d/'case',arcname='case')
 print(tag)
