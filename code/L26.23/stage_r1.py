#!/usr/bin/env python3
"""Stage R1 only in an absent root; S2 is immutable."""
import hashlib, pathlib, re, shutil, subprocess
S=pathlib.Path('/groups/kareem/[用户]/petw_runs/ubwp/r25_2_chew/S2_coarse/production')
R=pathlib.Path('/groups/kareem/[用户]/L26_23_NEARWALL_R1')
assert S.is_dir() and not R.exists(), 'Source absent or root already exists: stop, do not overwrite'
R.mkdir()
for p in ['case/0','case/constant','case/system','case/input']:
    shutil.copytree(S/p,R/p,symlinks=True)
shutil.copy2(S/'env.sh',R/'env.sh')
shutil.copy2(S/'config.sha256',R/'source_config.sha256')
old=(R/'case/0/nut').read_text()
new,n=re.subn(r'(\bbuilding\s*\{\s*type\s+)nutUSpaldingWallFunction(\s*;)',r'\1nutLowReWallFunction\2',old)
assert n==1 and old.replace('nutUSpaldingWallFunction','nutLowReWallFunction')==new
(R/'case/0/nut').write_text(new)
source=[]
for line in (S/'config.sha256').read_text().splitlines():
    h,p=line.split(maxsplit=1)
    p=p.strip()
    if p.startswith('*'): p=p[1:]
    source.append((h,p))
changes=[]
newlines=[]
for oldhash,p in source:
    assert (S/p).is_file(),p
    actual=hashlib.sha256((S/p).read_bytes()).hexdigest()
    assert actual==oldhash, f'S2 manifest mismatch {p}'
    if not (R/p).is_file():
        target_path=R/'source_immutable'/p
        target_path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(S/p,target_path)
    else:
        target_path=R/p
    target=hashlib.sha256(target_path.read_bytes()).hexdigest()
    newlines.append(f'{target}  {target_path.relative_to(R)}')
    if target!=oldhash: changes.append(p)
assert changes==['case/0/nut'], changes
(R/'config.sha256').write_text('\n'.join(newlines)+'\n')
(R/'scientific_diff.txt').write_text('source='+str(S)+'\nsource_manifest='+str(S/'config.sha256')+'\nchanged='+repr(changes)+'\nold_type=nutUSpaldingWallFunction\nnew_type=nutLowReWallFunction\n')
# A separate smoke copy: no baseline history, no baseline postProcessing.
shutil.copytree(R/'case',R/'smoke/case',symlinks=True)
p=R/'smoke/case/system/controlDict'
s=p.read_text()
s,n=re.subn(r'(?m)^(endTime\s+)44\.000000\s*;',r'\g<1>0.500000;',s)
assert n==1
p.write_text(s)
assert (R/'smoke/case/system/controlDict').read_text()!= (R/'case/system/controlDict').read_text()
print('ROOT',R,'SCIENTIFIC_DIFF',changes,'FILES',len(source),'SMOKE_READY')
