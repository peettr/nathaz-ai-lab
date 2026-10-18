#!/usr/bin/env python3
import subprocess,shlex
from pathlib import Path
R=Path(__file__).parent
code=(R/'inspect_remote.py').read_text()
ssh=['ssh','-o','ControlPath=~/.ssh/sockets/[邮箱]','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false','[邮箱]','nice -n 19 ionice -c3 python3 -c '+shlex.quote(code)]
with (R/'remote_pdf_representatives.jsonl').open('rb') as src,(R/'remote_pdf_inspection.jsonl').open('wb') as dst:
    proc=subprocess.run(ssh,stdin=src,stdout=dst,stderr=subprocess.PIPE,timeout=7200)
print('exit',proc.returncode,'stderr',proc.stderr.decode()[:2000])
