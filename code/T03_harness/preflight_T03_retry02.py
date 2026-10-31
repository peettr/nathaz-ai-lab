#!/usr/bin/env python3
"""Read-only static preflight for four fresh UGE roots; no solver."""
from pathlib import Path
import subprocess, hashlib, re, os
for tag in ('B0','B0prime','B1','REF'):
    root=Path(f'/groups/kareem/[用户]/L22_6/L22_6_T03_v12_{tag}_20261021_02')
    path=root/'run.sh'; txt=path.read_text()
    expect=f'ROOT={root}\nTAG={tag}\ncd "$ROOT" || exit 99\n'
    assert expect in txt and not re.search(r'\$\{T03_(?:ROOT|TAG)',txt)
    synt=subprocess.run(['env','-i','/bin/bash','-n',str(path)],capture_output=True,text=True)
    assert synt.returncode==0,synt.stderr
    fixture=expect+'test "$PWD" = "$ROOT" && test -f "$ROOT/run.sh" && test "$TAG" = '+tag+' && printf "checked %s %s\\n" "$TAG" "$PWD"\n'
    result=subprocess.run(['env','-i','/bin/bash','-c',fixture],capture_output=True,text=True,cwd='/users/[用户]')
    assert result.returncode==0,(result.stdout,result.stderr)
    assert not any((root/x).exists() for x in ('workflow.log','run.exitcode','stage.exitcodes','log.pimpleFoam'))
    assert (root/'EXPERIMENT_CARD.md').is_file()
    for folder in ('0','system','constant'):
        assert (root/folder).is_dir()
    print(tag,result.stdout.strip(),hashlib.sha256(path.read_bytes()).hexdigest())
