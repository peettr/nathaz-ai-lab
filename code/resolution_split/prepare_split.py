"""Prepare isolated Colab input decks; no solver runs locally."""
from pathlib import Path
import shutil, struct, hashlib, json, tarfile
R=Path(__file__).resolve().parent; P=R.parent
sources={'E1':P/'resolution_crop_v2/stage_C1v2','E05':P/'resolution_c05/stage_C05','C1G0':P/'resolution_crop_v2/stage_C1v2'}
for tag,src in sources.items():
 out=R/('stage_'+tag)
 assert not out.exists(),out
 shutil.copytree(src,out,ignore=shutil.ignore_patterns('bin','obj','RESULTS','*.vtk','*.log'))
 if tag.startswith('E'):
  stl=out/'case/proj_temp/CaseE_PF.stl'; raw=stl.read_bytes();n=struct.unpack_from('<I',raw,80)[0];assert len(raw)==84+50*n and n==2756
  # Keep the original 12 surrounding base triangles so STL reader has an extent;
  # ground TYPE_S is generated independently by setup.cpp.
  stl.write_bytes(raw[:80]+struct.pack('<I',12)+raw[-600:])
  conf=out/'case/conf.luwpf';s=conf.read_text().replace('casename = CaseE','casename = EmptyCaseE');conf.write_text(s)
 else:
  defs=out/'FluidX3D/src/defines.hpp';t=defs.read_text();assert t.count('//#define GROUND_WALL_MODEL')==1;defs.write_text(t.replace('//#define GROUND_WALL_MODEL','#define GROUND_WALL_MODEL'))
 files=['case/wind_bc/profile.dat','case/proj_temp/CaseE_PF.stl','case/conf.luwpf','FluidX3D/src/setup.cpp','FluidX3D/src/defines.hpp']
 manifest={f:hashlib.sha256((out/f).read_bytes()).hexdigest() for f in files}
 (R/(tag+'_manifest.json')).write_text(json.dumps(manifest,indent=2)+'\n')
 with tarfile.open(R/(tag+'_inputs.tar.gz'),'w:gz') as t:
  t.add(out/'FluidX3D',arcname='FluidX3D');t.add(out/'case',arcname='case')
 print(tag,manifest)
