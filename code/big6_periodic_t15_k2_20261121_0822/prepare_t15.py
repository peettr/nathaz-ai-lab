#!/usr/bin/env python3
"""Prepare isolated T15 k2 8H×4H stage from sealed Stage B; old roots read-only."""
from pathlib import Path
import tarfile,hashlib,json,difflib,shutil
R=Path(__file__).resolve().parent; P=R.parent
BASE=P/'stageB_run_20261119_2233'; D8=P/'domain8H_20261120_0110'
source=BASE/'t17b_stage.tar.gz'; assert source.is_file()
with tarfile.open(source) as t:
 members=[m for m in t if m.name=='pack_stage/periodic_t15_k2' or m.name.startswith('pack_stage/periodic_t15_k2/')]
 assert len(members)>10
 for m in members:
  assert '..' not in Path(m.name).parts and (m.isdir() or m.isfile())
  t.extract(m,R,filter='data')
src=R/'pack_stage/periodic_t15_k2/src'
p=src/'setup.cpp'; oldsetup=p.read_text(); assert oldsetup.count('LBM lbm(256u,128u,66u,units.nu(1.48e-5f),f_lattice);')==1
newsetup=oldsetup.replace('LBM lbm(256u,128u,66u,units.nu(1.48e-5f),f_lattice);','LBM lbm(512u,256u,66u,units.nu(1.48e-5f),f_lattice);')
p.write_text(newsetup)
# Ensure source physics and phase implementation identical to archived 8H×4H variant.
for n in ('kernel.cpp','lbm.cpp','defines.hpp','setup.cpp'):
 assert (src/n).read_bytes()==(D8/'pack_stage/periodic_t15_k2/src'/n).read_bytes(),n
p=src/'t17_b_native.inc'; old=p.read_text(); s=old
for before,after in (('const ulong initial=(mode=="smoke")?1000ul:5ul*Tsteps;','const ulong initial=(mode=="smoke")?1000ul:25ul*Tsteps;'),('advance(equilibrium_end,false);','advance(equilibrium_end,true);'),('capture(stats && step%sample_stride==0ul)','capture(step%sample_stride==0ul)'),('(stats && step%sample_stride==0ul)','(step%sample_stride==0ul)')):
 assert before in s,before;s=s.replace(before,after)
assert s!=old;p.write_text(s)
(R/'PRODUCER_DIFF.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),s.splitlines(True),fromfile='stageB_run/periodic_t15_k2/src/t17_b_native.inc',tofile='big6_t15/periodic_t15_k2/src/t17_b_native.inc')))
(R/'SETUP_DIFF.patch').write_text(''.join(difflib.unified_diff(oldsetup.splitlines(True),newsetup.splitlines(True),fromfile='stageB_run/periodic_t15_k2/src/setup.cpp',tofile='big6_t15/periodic_t15_k2/src/setup.cpp')))
with tarfile.open(R/'stage_big6.tar.gz','w:gz') as t:t.add(R/'pack_stage',arcname='pack_stage')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
manifest={'archive_sha256':sha(R/'stage_big6.tar.gz'),'source_files':{n:sha(src/n) for n in ('setup.cpp','kernel.cpp','lbm.cpp','defines.hpp','t17_b_native.inc')},'reference_stageB_archive_sha256':sha(source),'reference_domain8H_source':json.loads((D8/'longspin_manifest.json').read_text())['source_files']}
(R/'manifest_big6.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
