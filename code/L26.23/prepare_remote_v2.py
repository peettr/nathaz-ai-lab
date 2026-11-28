#!/usr/bin/env python3
"""One-shot, no overwrite: prepare R1 nutcheck and unsubmitted production roots."""
from pathlib import Path
import shutil,re,hashlib
R=Path('/groups/kareem/[用户]/L26_23_NEARWALL_R1')
S=Path('/groups/kareem/[用户]/petw_runs/ubwp/r25_2_chew/S2_coarse/production')
assert R.is_dir() and S.is_dir()
for kind in ('nutcheck','prod_prep'):
    dest=R/kind
    assert not dest.exists(),f'existing root: {dest}'
for kind in ('nutcheck','prod_prep'):
    dest=R/kind
    dest.mkdir()
    shutil.copytree(R/'case',dest/'case',symlinks=True)
    shutil.copy2(R/'env.sh',dest/'env.sh')
    if kind=='prod_prep':
        for name in ('config.sha256','scientific_diff.txt'):
            shutil.copy2(R/name,dest/name)
        # manifest immutable paths were not inside case; retain identical paths/hashes.
        shutil.copytree(R/'source_immutable',dest/'source_immutable',symlinks=True)
        shutil.copy2(S/'library.sha256',dest/'library.sha256')
    else:
        p=dest/'case/system/controlDict'
        text=p.read_text()
        for old,new in ((r'(?m)^(endTime\s+)44\.000000\s*;',r'\g<1>0.002000;'),
                        (r'(?m)^(writeInterval\s+)2\s*;',r'\g<1>0.002;'),
                        (r'(?m)^(writeFormat\s+)binary\s*;',r'\g<1>ascii;')):
            text,n=re.subn(old,new,text);assert n==1,(old,n)
        p.write_text(text)
    print('PREPARED',dest)
