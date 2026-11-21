#!/usr/bin/env python3
"""Stage only new E2/E3 CPU roots via an existing CRC master; refuse overwrites."""
import hashlib, pathlib, subprocess, shlex
LOCAL=pathlib.Path(__file__).resolve().parent
PREF=LOCAL.parent/'k_gc37_preflight'
BASE='/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37'
HOST='[邮箱]';SOCK='./.ssh/sockets/[邮箱]'
SSH=['ssh','-o',f'ControlPath={SOCK}','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false','-o','ConnectTimeout=15',HOST]
LEVELS='1000,975,950,925,900,850,800,750,700,650,600,550,500,450,400,350,300,250,200,150,100,70,50,30,20,10,7,5,3,2,1\n'
def remote(s, payload=None):
 p=subprocess.run(SSH+[s],input=payload,capture_output=True,timeout=120)
 if p.returncode:raise RuntimeError((s,p.returncode,p.stderr.decode(errors='replace')[-2000:]))
 return p.stdout.decode(errors='replace')
def main():
 assert pathlib.Path(SOCK).is_socket()
 check=subprocess.run(['ssh','-O','check','-o',f'ControlPath={SOCK}',HOST],capture_output=True,timeout=20)
 assert check.returncode==0 and b'Master running' in check.stderr
 assert 'OK' in remote('echo OK')
 for event in ('E2','E3'):
  r=f'{BASE}/drivers_gc37_{event}_v1/ops_cpu_{event}_v1'
  assert remote('if test -e '+shlex.quote(r)+'; then echo EXISTS; else echo ABSENT; fi').strip()=='ABSENT',r
  remote('mkdir -p '+shlex.quote(r))
  files={'build_gc37_wps_crc_cpu_e2e3_v2.py':LOCAL/'build_gc37_wps_crc_cpu_e2e3_v2.py',
    'wps_format5.py':PREF/'wps_format5.py',
    'event_times_gc37.json':LOCAL/'event_times_gc37.json',
    'domain_bbox_gc37.json':LOCAL/'domain_bbox_gc37.json',
    f'submit_gc37_{event.lower()}_cpu_v1.sh':LOCAL/f'submit_gc37_{event.lower()}_cpu_v1.sh'}
  for name,path in files.items():
   data=path.read_bytes();remote('umask 027; (set -C; cat > '+shlex.quote(r+'/'+name)+')',data)
   sha=remote('sha256sum '+shlex.quote(r+'/'+name)).split()[0]
   assert sha==hashlib.sha256(data).hexdigest(),(event,name)
   print('STAGED',event,name,sha,flush=True)
  remote('umask 027; (set -C; cat > '+shlex.quote(r+'/COMMON_LEVELS.txt')+')',LEVELS.encode())
  source=f'{BASE}/inputs_2024_E2E3_resume_v2/raw'
  remote('ln -s '+shlex.quote(source)+' '+shlex.quote(r+'/raw'))
  assert remote('test -s '+shlex.quote(r+'/raw/gfs.0p25.2024051818.f000.grib2')+' && echo OK').strip().endswith('OK')
  print('ROOT_READY',event,r,flush=True)
if __name__=='__main__':main()
