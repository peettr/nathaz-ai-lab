#!/usr/bin/env python3
"""Prepare T17 large-domain T4 from immutable Stage B and domain8H archives."""
from pathlib import Path
import tarfile,hashlib,json,difflib,shutil
R=Path(__file__).resolve().parent
BASE=R.parent/'stageB_run_20261119_2233'
D8=R.parent/'domain8H_20261120_0110'
source=BASE/'t17b_stage.tar.gz'
assert source.is_file() and D8.is_dir()
with tarfile.open(source) as t:
    members=[m for m in t if m.name=='pack_stage/periodic_t4' or m.name.startswith('pack_stage/periodic_t4/')]
    assert len(members)>10
    for m in members:
        assert '..' not in Path(m.name).parts and (m.isdir() or m.isfile())
        target=R/m.name
        if not target.exists(): t.extract(m,R,filter='data')
src=R/'pack_stage/periodic_t4/src'
def edit(name,old,new):
    p=src/name;s=p.read_text()
    if s.count(new)==1 and s.count(old)==0:return
    assert s.count(old)==1,(name,s.count(old));p.write_text(s.replace(old,new))
edit('setup.cpp','LBM lbm(256u,128u,66u,units.nu(1.48e-5f),f_lattice);','LBM lbm(512u,256u,66u,units.nu(1.48e-5f),f_lattice);')
p=src/'t17_b_native.inc';old=p.read_text();s=old
for before,after in (
 ('const ulong initial=(mode=="smoke")?1000ul:5ul*Tsteps;','const ulong initial=(mode=="smoke")?1000ul:25ul*Tsteps;'),
 ('advance(equilibrium_end,false);','advance(equilibrium_end,true);'),
 ('capture(stats && step%sample_stride==0ul)','capture(step%sample_stride==0ul)'),
 ('(stats && step%sample_stride==0ul)','(step%sample_stride==0ul)')):
    assert before in s,before;s=s.replace(before,after)
# The producer must capture both planes and full profiles throughout spin-up.
s=s.replace('if(stats) profile[zz]+=', 'if(stats) profile[zz]+=')
assert s!=old
p.write_text(s)
(R/'PRODUCER_DIFF.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),s.splitlines(True),fromfile='stageB_run/periodic_t4/src/t17_b_native.inc',tofile='big6_t4/periodic_t4/src/t17_b_native.inc')))
with tarfile.open(R/'stage_big6.tar.gz','w:gz') as t:t.add(R/'pack_stage',arcname='pack_stage')
def sha(p):
 h=hashlib.sha256();
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
manifest={'archive_sha256':sha(R/'stage_big6.tar.gz'),'source_files':{n:sha(src/n) for n in ('setup.cpp','kernel.cpp','lbm.cpp','defines.hpp','t17_b_native.inc')},'reference_stageB_archive_sha256':sha(source),'reference_domain8H_source':json.loads((D8/'longspin_manifest.json').read_text())['source_files']}
(R/'manifest_big6.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
