#!/usr/bin/env python3
import pathlib,shutil,json,hashlib,tarfile,datetime,difflib
B=pathlib.Path(__file__).resolve().parent
old=B/'diagFP32_20261119_185915'
r=B/('diagFP32_v2_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
r.mkdir();shutil.copytree(old/'stage',r/'stage')
for n in ['worker_diag.py','controller_diag.py','remote_diag.py','dry_run.py','stub_solver.py','machine.py']:
 shutil.copy2(old/n,r/n)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
source={n:sha(r/'stage/src'/n) for n in ['kernel.cpp','lbm.cpp','setup.cpp','defines.hpp']}
base=B/'stageA13_20261119_1421/work/pack_stage/periodic_t4/src'
assert source['kernel.cpp']==sha(base/'kernel.cpp') and source['lbm.cpp']==sha(base/'lbm.cpp')
for n in ['setup.cpp','defines.hpp']:
 (r/(n+'.diff')).write_text(''.join(difflib.unified_diff((base/n).read_text().splitlines(True),(r/'stage/src'/n).read_text().splitlines(True),fromfile='A13/'+n,tofile='D5D6/'+n)))
with tarfile.open(r/'diag_stage.tar.gz','w:gz') as t:t.add(r/'stage',arcname='stage')
(r/'diag_manifest.json').write_text(json.dumps({'archive_sha256':sha(r/'diag_stage.tar.gz'),'source_sha256':source},indent=2)+'\n')
(r/'PREFLIGHT.ok').write_text(json.dumps({n:sha(r/n) for n in ['controller_diag.py','worker_diag.py','remote_diag.py','diag_stage.tar.gz','diag_manifest.json','machine.py']},indent=2)+'\n')
(r/'SOURCE_PROVENANCE.json').write_text(json.dumps({'A13_kernel_sha':sha(base/'kernel.cpp'),'A13_lbm_sha':sha(base/'lbm.cpp'),'D5D6_source':source,'D5':'U(z)=Ubar+A sin(2pi(z+0.5)/66); Ubar=[Ulog(0.5)+Ulog(63.5)]/2, A=[Ulog(63.5)-Ulog(0.5)]/2','D6':'U(z)=Ubar; all z periodic, no solids, F=0'},indent=2)+'\n')
print(r)
