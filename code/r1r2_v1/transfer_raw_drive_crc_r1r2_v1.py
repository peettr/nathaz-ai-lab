#!/usr/bin/env python3
"""Stream verified Drive forecast fields to CRC through existing master; never stage NPZ on 工作站."""
import hashlib, json, subprocess, shlex, sys
from pathlib import Path
SRC='gdrive:colab_cache/r234c_r1r2_forecasts_v1/'
ROOT='/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37'
SOCK='./.ssh/sockets/[邮箱]'
SSH=['ssh','-o',f'ControlPath={SOCK}','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false','-o','ConnectTimeout=20','[邮箱]']
CYCLES={'R1':{'2024073100':5,'2024073000':9,'2024072900':13},'R2':{'2024060318':5,'2024060218':9,'2024060118':13}}
def run(argv,**kw): return subprocess.run(argv,check=True,**kw)
run(['ssh','-O','check','-o',f'ControlPath={SOCK}','[邮箱]'],stdout=subprocess.DEVNULL)
run(SSH+['echo OK'],stdout=subprocess.DEVNULL)
for ev,cycles in CYCLES.items():
 for cycle,steps in cycles.items():
  source=SRC+cycle+'/'
  data=run(['rclone','cat',source+'RAW_MANIFEST.json'],capture_output=True).stdout
  entries=json.loads(data)
  assert len(entries)==steps and [x['file'] for x in entries]==[f'step_{i:02d}.npz' for i in range(1,steps+1)]
  dest=f'{ROOT}/gc37_raw_{ev}_v1/{cycle}'
  run(SSH+[f'mkdir -p {shlex.quote(dest)}'])
  for item in entries:
   name=item['file'];path=f'{dest}/{name}';expected=item['sha256'];size=item['bytes']
   probe=run(SSH+[f'if test -e {shlex.quote(path)}; then sha256sum {shlex.quote(path)}; else echo ABSENT; fi'],capture_output=True,text=True).stdout.strip()
   if probe=='ABSENT':
    reader=subprocess.Popen(['rclone','cat',source+name],stdout=subprocess.PIPE)
    assert reader.stdout is not None
    writer=subprocess.run(SSH+[f'(set -C; cat > {shlex.quote(path)})'],stdin=reader.stdout)
    reader.stdout.close();rc=reader.wait()
    if rc or writer.returncode: raise RuntimeError(('transfer',cycle,name,rc,writer.returncode))
   elif probe.split()[0]!=expected: raise RuntimeError(('existing_mismatch',path,probe,expected))
   verify=run(SSH+[f'stat -c %s {shlex.quote(path)}; sha256sum {shlex.quote(path)}'],capture_output=True,text=True).stdout.splitlines()
   assert int(verify[0])==size and verify[1].split()[0]==expected,(path,verify,item)
   print('VERIFIED',cycle,name,flush=True)
  sums=''.join(f"{x['sha256']}  {x['file']}\n" for x in entries)
  local_sha=hashlib.sha256(sums.encode()).hexdigest()
  sumfile=f'{dest}/SHA256SUMS'
  probe=run(SSH+[f'if test -e {shlex.quote(sumfile)}; then sha256sum {shlex.quote(sumfile)}; else echo ABSENT; fi'],capture_output=True,text=True).stdout.strip()
  if probe=='ABSENT':
   run(SSH+[f'(set -C; cat > {shlex.quote(sumfile)})'],input=sums.encode())
  elif probe.split()[0]!=local_sha: raise RuntimeError(('existing_sums_mismatch',sumfile))
  run(SSH+[f'cd {shlex.quote(dest)} && sha256sum -c SHA256SUMS'],stdout=subprocess.DEVNULL)
  print('CYCLE_OK',ev,cycle,steps,local_sha,flush=True)
print('ALL_RAW_VERIFIED',flush=True)
