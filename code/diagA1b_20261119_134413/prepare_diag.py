#!/usr/bin/env python3
import pathlib,tarfile,hashlib,json,difflib,shutil
R=pathlib.Path(__file__).resolve().parent; old=pathlib.Path((R/'ORIGIN.txt').read_text().strip());src=R/'pack_stage/periodic_t15_k2'; packaged=R/'stage';shutil.copytree(src,packaged,ignore=shutil.ignore_patterns('bin','temp','*.o'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
with tarfile.open(R/'diag_stage.tar.gz','w:gz') as t:t.add(packaged,arcname='stage')
files=['setup.cpp','kernel.cpp','lbm.cpp','defines.hpp'];manifest={'archive_sha256':sha(R/'diag_stage.tar.gz'),'source_sha256':{n:sha(packaged/'src'/n) for n in files}};(R/'diag_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
a=(old/'dry_content/t17/pack_stage/periodic_t15_k2/src/setup.cpp').read_text().splitlines(True);b=(packaged/'src/setup.cpp').read_text().splitlines(True);(R/'SETUP_DIAG.diff').write_text(''.join(difflib.unified_diff(a,b,fromfile='A12/setup.cpp',tofile='diagnosis/setup.cpp')))
print(json.dumps(manifest,indent=2))
