"""Create private E1G0A35/A70 decks. Only file preparation on 工作站."""
from pathlib import Path
import shutil, tarfile, hashlib, json
R=Path(__file__).resolve().parent
base=R.parent/'approach_keep/stage_E1G0'
assert base.exists()
for tag in ('E1G0A35','E1G0A70'):
    out=R/('stage_'+tag)
    assert not out.exists(),out
    shutil.copytree(base,out,ignore=shutil.ignore_patterns('bin','obj','RESULTS','*.vtk','*.log'))
    files=['case/wind_bc/profile.dat','case/proj_temp/CaseE_PF.stl','case/conf.luwpf','FluidX3D/src/setup.cpp','FluidX3D/src/defines.hpp','FluidX3D/src/kernel.cpp','FluidX3D/src/lbm.cpp','FluidX3D/src/lbm.hpp']
    manifest={f:hashlib.sha256((out/f).read_bytes()).hexdigest() for f in files}
    (R/(tag+'_manifest.json')).write_text(json.dumps(manifest,indent=2)+'\n')
    with tarfile.open(R/(tag+'_inputs.tar.gz'),'w:gz') as t:
        t.add(out/'FluidX3D',arcname='FluidX3D'); t.add(out/'case',arcname='case')
    print(tag, manifest)
