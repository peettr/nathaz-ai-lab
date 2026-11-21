#!/usr/bin/env python3
"""One-shot, fresh root for approved nutcheck environment recovery."""
from pathlib import Path
import shutil,re
base=Path('/groups/kareem/[用户]/L26_23_NEARWALL_R1')
root=base/'nutcheck_v2'
assert base.is_dir() and (base/'case').is_dir() and (base/'env.sh').is_file()
assert not root.exists(),f'refuse existing root: {root}'
root.mkdir()
shutil.copytree(base/'case',root/'case',symlinks=True)
shutil.copy2(base/'env.sh',root/'env.sh')
p=root/'case/system/controlDict'
text=p.read_text()
for old,new in ((r'(?m)^(endTime\s+)44\.000000\s*;',r'\g<1>0.002000;'),
                (r'(?m)^(writeInterval\s+)2\s*;',r'\g<1>0.002;'),
                (r'(?m)^(writeFormat\s+)binary\s*;',r'\g<1>ascii;')):
    text,n=re.subn(old,new,text)
    assert n==1,(old,n)
p.write_text(text)
print('PREPARED',root)
