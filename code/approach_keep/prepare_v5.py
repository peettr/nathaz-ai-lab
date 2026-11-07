"""Propagate WALE_SGS host define to generated OpenCL source."""
from pathlib import Path
import shutil,tarfile,hashlib,json
R=Path(__file__).resolve().parent
for base in ('E1Wv4','E1G0Wv4'):
 tag=base.replace('v4','v5');old=R/('stage_'+base);out=R/('stage_'+tag)
 assert old.exists() and not out.exists();shutil.copytree(old,out)
 p=out/'FluidX3D/src/lbm.cpp';s=p.read_text();i=s.index('#ifdef SUBGRID\n',s.index('string LBM_Domain::device_defines()'))
 s=s[:i]+'#ifdef WALE_SGS\n\t"\\n\\t#define WALE_SGS"\n#endif\n'+s[i:];p.write_text(s)
 files=['case/wind_bc/profile.dat','case/proj_temp/CaseE_PF.stl','case/conf.luwpf','FluidX3D/src/setup.cpp','FluidX3D/src/defines.hpp','FluidX3D/src/kernel.cpp','FluidX3D/src/lbm.cpp','FluidX3D/src/lbm.hpp']
 (R/(tag+'_manifest.json')).write_text(json.dumps({f:hashlib.sha256((out/f).read_bytes()).hexdigest() for f in files},indent=2)+'\n')
 with tarfile.open(R/(tag+'_inputs.tar.gz'),'w:gz') as t:t.add(out/'FluidX3D',arcname='FluidX3D');t.add(out/'case',arcname='case')
 print(tag)
