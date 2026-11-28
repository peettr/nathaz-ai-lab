#!/usr/bin/env python3
"""Stage the bounce-only 8H×4H two-seed run without touching archived roots."""
from pathlib import Path
import hashlib,json,tarfile,difflib
R=Path(__file__).resolve().parent
src=R/'pack_stage/periodic_bounce/src'
def change(path, old, new):
    p=src/path;s=p.read_text();assert s.count(old)==1 or new in s,(path,old,s.count(old));p.write_text(s.replace(old,new))
change('setup.cpp','LBM lbm(256u,128u,66u,units.nu(1.48e-5f),f_lattice);','LBM lbm(512u,256u,66u,units.nu(1.48e-5f),f_lattice);')
p=src/'t17_b_native.inc';s=p.read_text();original=s
s=s.replace('const ulong initial=(mode=="smoke")?1000ul:5ul*Tsteps;', 'const ulong initial=(mode=="smoke")?1000ul:25ul*Tsteps;')
s=s.replace('// Only the statistics interval writes plane frames; no sample is copied to 工作站.', '// Retain full-run planes on VM for descriptive 2T windows; no binary plane download.')
s=s.replace('advance(equilibrium_end,false);','advance(equilibrium_end,true);')
s=s.replace('capture(stats && step%sample_stride==0ul)', 'capture(step%sample_stride==0ul)')
s=s.replace('if(step%ledger_stride==0ul || step==target || (stats && step%sample_stride==0ul))', 'if(step%ledger_stride==0ul || step==target || step%sample_stride==0ul)')
assert s!=original
assert 'production")?1000ul:5ul*Tsteps' not in s
p.write_text(s)
(R/'PRODUCER_DIFF.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),s.splitlines(True),fromfile='stageB_run/periodic_bounce/src/t17_b_native.inc',tofile='big6/periodic_bounce/src/t17_b_native.inc')))
with tarfile.open(R/'stage_big6.tar.gz','w:gz') as tar:tar.add(R/'pack_stage',arcname='pack_stage')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest={'archive_sha256':sha(R/'stage_big6.tar.gz'),'source_files':{n:sha(src/n) for n in ('setup.cpp','kernel.cpp','lbm.cpp','defines.hpp','t17_b_native.inc')}}
(R/'manifest_big6.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
