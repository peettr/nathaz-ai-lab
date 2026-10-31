"""Create fresh corrected WALE decks after C++ access-control failure."""
from pathlib import Path
import shutil,tarfile,hashlib,json
R=Path(__file__).resolve().parent
for base in ('E1W','E1G0W'):
 tag=base+'v2';old=R/('stage_'+base);out=R/('stage_'+tag)
 assert old.exists() and not out.exists()
 shutil.copytree(old,out)
 src=out/'FluidX3D/src';p=src/'lbm.cpp';s=p.read_text()
 a='lbm_domain[d]->kernel_wale_omega.enqueue_run()';assert s.count(a)==1
 s=s.replace(a,'lbm_domain[d]->enqueue_wale_omega()')
 key='void LBM_Domain::enqueue_stream_collide() {';assert s.count(key)==1
 s=s.replace(key,'#ifdef WALE_SGS\nvoid LBM_Domain::enqueue_wale_omega() { kernel_wale_omega.enqueue_run(); }\n#endif\n'+key);p.write_text(s)
 p=src/'lbm.hpp';s=p.read_text();key='\tvoid enqueue_stream_collide();';assert s.count(key)==1
 s=s.replace(key,'#ifdef WALE_SGS\n\tvoid enqueue_wale_omega();\n#endif\n'+key);p.write_text(s)
 files=['case/wind_bc/profile.dat','case/proj_temp/CaseE_PF.stl','case/conf.luwpf','FluidX3D/src/setup.cpp','FluidX3D/src/defines.hpp','FluidX3D/src/kernel.cpp','FluidX3D/src/lbm.cpp','FluidX3D/src/lbm.hpp']
 (R/(tag+'_manifest.json')).write_text(json.dumps({f:hashlib.sha256((out/f).read_bytes()).hexdigest() for f in files},indent=2)+'\n')
 with tarfile.open(R/(tag+'_inputs.tar.gz'),'w:gz') as t:t.add(out/'FluidX3D',arcname='FluidX3D');t.add(out/'case',arcname='case')
 print(tag)
