#!/usr/bin/env python3
"""Stage five independent Blackwell recovery roots without touching outputs."""
from pathlib import Path
import hashlib
import json
import subprocess
import tarfile

HERE=Path(__file__).resolve().parent
REMOTE=Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x')
CASES=[('N3','24h','2022070418'),('N3','48h','2022070318'),('N3','72h','2022070218'),('N4','24h','2022042200'),('N4','48h','2022042100')]
BASE=HERE/'recover_N1_72_v3.sub'
SCRIPT=(HERE/'run_recover_N1_72_v3.sh').read_text()
SUB=BASE.read_text()
PY=(HERE/'resume_single_blackwell_b1_v3.py').read_bytes()
assert all(len(c)==10 for _,_,c in CASES)
assert 'N1 --lead 72h' in SCRIPT
assert 'recover_N1_72_v3' in SCRIPT and 'recover_N1_72_v3' in SUB
assert 'request_memory = 131072 MB' in SUB and 'request_gpus = 1' in SUB
stage=HERE/'stage_recover_remaining_v3'
assert not stage.exists(),stage
stage.mkdir()
manifest={}
for event,lead,cycle in CASES:
    tag=f'{event}_{lead[:-1]}'
    dirname=f'infer_b1_blackwell_recover_{tag}_v3'
    root=stage/dirname
    root.mkdir()
    s=SCRIPT.replace('infer_b1_blackwell_recover_N1_72_v3',dirname).replace('--event N1 --lead 72h',f'--event {event} --lead {lead}')
    q=SUB.replace('infer_b1_blackwell_recover_N1_72_v3',dirname).replace('recover_N1_72_v3',f'recover_{tag}_v3').replace('R234c_GC37x_B1_recover_N1_72_v3',f'R234c_GC37x_B1_recover_{tag}_v3')
    assert str(REMOTE/dirname) in s and str(REMOTE/dirname) in q
    files={f'run_recover_{tag}_v3.sh':s.encode(),f'recover_{tag}_v3.sub':q.encode(),'resume_single_blackwell_b1_v3.py':PY}
    for name,data in files.items():
        (root/name).write_bytes(data)
    subprocess.run(['bash','-n',str(root/f'run_recover_{tag}_v3.sh')],check=True)
    subprocess.run(['python3','-m','py_compile',str(root/'resume_single_blackwell_b1_v3.py')],check=True)
    manifest[tag]={'cycle':cycle,'root':str(REMOTE/dirname),'files':{name:hashlib.sha256(data).hexdigest() for name,data in files.items()}}
(stage/'STAGING_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
archive=HERE/'recover_remaining_v3.tar.gz'
assert not archive.exists(),archive
with tarfile.open(archive,'w:gz') as tf:
    for path in sorted(stage.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            tf.add(path,arcname=str(path.relative_to(stage)))
print(archive)
print(json.dumps(manifest,indent=2))
