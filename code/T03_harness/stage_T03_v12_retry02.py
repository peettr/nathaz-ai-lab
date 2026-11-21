#!/usr/bin/env python3
"""Stage retry in four fresh CRC roots from frozen first-attempt inputs only."""
from pathlib import Path
import json, shutil, hashlib
base=Path('/users/[用户]')
tags=('B0','B0prime','B1','REF')
for tag in tags:
    old=base/f'L22_6_T03_v12_{tag}_20261021_01'
    new=base/f'L22_6_T03_v12_{tag}_20261021_02'
    assert old.is_dir() and not new.exists(), (old,new)
    new.mkdir(mode=0o700)
    for folder in ('0','system','constant'):
        shutil.copytree(old/folder,new/folder)
    original=(old/'run.sh').read_text()
    assert 'ROOT=${T03_ROOT:?}\nTAG=${T03_TAG:?}' in original
    text=original.replace('ROOT=${T03_ROOT:?}\nTAG=${T03_TAG:?}',f'ROOT={new}\nTAG={tag}',1)
    text=text.replace('# Unique case root and TAG are supplied by a frozen wrapper in each run root.', '# Frozen literal root and tag; no scheduler-exported variables required.')
    assert text.count(f'ROOT={new}')==1 and text.count(f'TAG={tag}')==1
    (new/'run.sh').write_text(text); (new/'run.sh').chmod(0o700)
    info=json.loads((old/'stage.json').read_text());info['retry_root']=str(new);info['source_attempt']=str(old)
    (new/'stage.json').write_text(json.dumps(info,indent=2)+'\n')
    print(tag,new,hashlib.sha256((new/'run.sh').read_bytes()).hexdigest())
