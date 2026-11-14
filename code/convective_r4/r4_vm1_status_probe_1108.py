import pathlib, subprocess, hashlib, os, json, shutil
r=pathlib.Path('/content/r4_s2')
print('processes',subprocess.run(['ps','-eo','pid,args'],capture_output=True,text=True).stdout.splitlines()[-15:],flush=True)
print('space_gb',round(shutil.disk_usage('/content').free/1e9,2),flush=True)
for name in ['vm1_1108.launch','vm1_1108.exit','vm1_1108.failed','s2_0_110.diskstop','s2_0_110.done','incremental_0_110.jsonl']:
 p=r/name
 print(name,'exists',p.exists(),'bytes',p.stat().st_size if p.exists() else None,'text',p.read_text()[:300] if p.exists() and name.endswith(('.exit','.failed','.diskstop','.done')) else '',flush=True)
p=r/'vm1_1108.log'
print('LOGTAIL',p.read_text(errors='replace').splitlines()[-12:] if p.exists() else [],flush=True)
