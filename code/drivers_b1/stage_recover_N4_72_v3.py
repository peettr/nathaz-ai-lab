#!/usr/bin/env python3
"""Prepare distinct N4 72h recovery package without altering previous roots."""
from pathlib import Path
import hashlib, tarfile, subprocess
H=Path(__file__).resolve().parent
B='/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x'
name='infer_b1_blackwell_recover_N4_72_v3'
root=H/'stage_recover_N4_72_v3'/name
assert not root.exists()
root.mkdir(parents=True)
s=(H/'run_recover_N1_72_v3.sh').read_text().replace('infer_b1_blackwell_recover_N1_72_v3',name).replace('--event N1 --lead 72h','--event N4 --lead 72h')
q=(H/'recover_N1_72_v3.sub').read_text().replace('infer_b1_blackwell_recover_N1_72_v3',name).replace('recover_N1_72_v3','recover_N4_72_v3').replace('R234c_GC37x_B1_recover_N1_72_v3','R234c_GC37x_B1_recover_N4_72_v3')
assert B+'/'+name in s and B+'/'+name in q
for n,data in [('run_recover_N4_72_v3.sh',s.encode()),('recover_N4_72_v3.sub',q.encode()),('resume_single_blackwell_b1_v3.py',(H/'resume_single_blackwell_b1_v3.py').read_bytes())]:
    (root/n).write_bytes(data)
    print(n,hashlib.sha256(data).hexdigest())
subprocess.run(['bash','-n',str(root/'run_recover_N4_72_v3.sh')],check=True)
subprocess.run(['python3','-m','py_compile',str(root/'resume_single_blackwell_b1_v3.py')],check=True)
archive=H/'recover_N4_72_v3.tar.gz'
assert not archive.exists()
with tarfile.open(archive,'w:gz') as tf:
    for p in root.iterdir():
        if p.is_file(): tf.add(p,arcname=name+'/'+p.name)
print(archive)
