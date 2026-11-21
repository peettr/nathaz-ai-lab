#!/usr/bin/env python3
"""Upload frozen independent E2/E3 readback to both new roots, no overwrites."""
import hashlib,pathlib,subprocess,shlex
HERE=pathlib.Path(__file__).resolve().parent
SOCK='./.ssh/sockets/[邮箱]'
HOST='[邮箱]';SSH=['ssh','-o',f'ControlPath={SOCK}','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false','-o','ConnectTimeout=15',HOST]
assert pathlib.Path(SOCK).is_socket()
p=subprocess.run(['ssh','-O','check','-o',f'ControlPath={SOCK}',HOST],capture_output=True,timeout=20);assert p.returncode==0
for e in ('E2','E3'):
 root=f'/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37/drivers_gc37_{e}_v1/ops_cpu_{e}_v1'
 for name,src in [('validate_gc37_wps_E2E3_v1.py',HERE/'validate_gc37_wps_E2E3_v1.py'),('EXPERIMENT_CARD_E2E3.md',HERE/'EXPERIMENT_CARD_E2E3.md')]:
  data=src.read_bytes();cmd='umask 027; (set -C; cat > '+shlex.quote(root+'/'+name)+'); sha256sum '+shlex.quote(root+'/'+name)
  result=subprocess.run(SSH+[cmd],input=data,capture_output=True,timeout=90)
  assert result.returncode==0,result.stderr.decode(errors='replace')
  sha=result.stdout.decode().split()[0];assert sha==hashlib.sha256(data).hexdigest()
  print(e,name,sha,flush=True)
