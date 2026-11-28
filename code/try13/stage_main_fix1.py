#!/usr/bin/env python3
"""Stage only the missing-newline engineering correction; no solver on 工作站."""
from pathlib import Path
import shutil, hashlib, json, tarfile, difflib
r=Path(__file__).resolve().parent
old=r/'main_stage'
new=r/'main_smoke_fix1/stage_t4'
assert old.is_dir() and not new.exists()
new.parent.mkdir(exist_ok=True)
shutil.copytree(old,new)
h=new/'FluidX3D_on/src/lbm.hpp'
a=h.read_text()
assert a.count('#endifvoid enqueue_initialize();')==1
b=a.replace('#endifvoid enqueue_initialize();','#endif\n\tvoid enqueue_initialize();')
h.write_text(b)
(new.parent/'lbm_hpp_newline.patch').write_text(''.join(difflib.unified_diff(a.splitlines(True),b.splitlines(True),fromfile='main_stage/lbm.hpp',tofile='fix1/lbm.hpp')))
assert '#endifvoid' not in b and '#endif\n\tvoid enqueue_initialize();' in b
manifest=new/'try13_source_manifest.json'
m=json.loads(manifest.read_text())
m['lbm.hpp']=hashlib.sha256(h.read_bytes()).hexdigest()
manifest.write_text(json.dumps(m,indent=2)+'\n')
archive=r/'main_smoke_fix1/try13_main_stage_fix1.tar.gz'
with tarfile.open(archive,'w:gz') as tar: tar.add(new,arcname='stage_t4')
outer={'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'source_sha256':{n:hashlib.sha256((new/'FluidX3D_on/src'/n).read_bytes()).hexdigest() for n in ('setup.cpp','kernel.cpp','lbm.cpp','lbm.hpp','defines.hpp')}}
(new.parent/'try13_main_archive_fix1.json').write_text(json.dumps(outer,indent=2)+'\n')
print(json.dumps({'archive':str(archive),'archive_sha256':outer['archive_sha256'],'corrected_lbm_hpp_sha256':m['lbm.hpp'],'members':len(tarfile.open(archive).getmembers())},indent=2))
