#!/usr/bin/env python3
import subprocess,shlex
from pathlib import Path
R=Path(__file__).parent
code=(R/'hash_candidates.py').read_text()
ssh=['ssh','-o','ControlPath=~/.ssh/sockets/[邮箱]','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false','[邮箱]','nice -n 19 ionice -c3 python3 -c '+shlex.quote(code)]
with (R/'remote_candidates.jsonl').open('rb') as src,(R/'remote_hashes.jsonl').open('wb') as dst:
    proc=subprocess.run(ssh,stdin=src,stdout=dst,stderr=subprocess.PIPE,timeout=3600)
print('remote exit',proc.returncode,'stderr',proc.stderr.decode()[:1000])
with (R/'local_candidates.jsonl').open('rb') as src,(R/'local_hashes.jsonl').open('wb') as dst:
    proc=subprocess.run(['python3',str(R/'hash_candidates.py')],stdin=src,stdout=dst,stderr=subprocess.PIPE,timeout=3600)
print('local exit',proc.returncode,'stderr',proc.stderr.decode()[:1000])
