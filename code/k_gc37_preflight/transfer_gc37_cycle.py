#!/usr/bin/env python3
"""Copy one completed cycle's cropped NPZ files to new CRC raw directory; verify each."""
import argparse,hashlib,json,pathlib,subprocess,shlex
B=pathlib.Path('./23_AI_Weather/06_Logs/k_gc37_preflight')
CFG=B/'colab_state_60b2bf75.json'; SESSION='r234c-gc37-60b2bf75'
REMOTE='/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37/gc37_raw_v1'
HOST='[邮箱]'; SOCK='./.ssh/sockets/[邮箱]'
SSH=['ssh','-n','-o',f'ControlPath={SOCK}','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false','-o','ConnectTimeout=20',HOST]
SCP=['scp','-o',f'ControlPath={SOCK}','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false','-o','ConnectTimeout=20']
COLAB=['colab','--auth','oauth2','--config',str(CFG)]
def run(cmd):
 p=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=240)
 if p.returncode:raise RuntimeError((cmd,p.returncode,p.stdout[-400:],p.stderr[-400:]))
 return p.stdout
def download(src,dst):
 if dst.exists():raise FileExistsError(dst)
 run(COLAB+['download','-s',SESSION,src,str(dst)])
def sha(path):
 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main(cycle):
 run(['ssh','-O','check','-o',f'ControlPath={SOCK}',HOST])
 local=B/f'RAW_MANIFEST_{cycle}.json'
 download(f'/content/r234c_gc37_60b2bf75/RAW_MANIFEST_{cycle}.json',local)
 items=json.loads(local.read_text()); expected={'2020060806':5,'2020060706':9,'2020060606':13}[cycle]
 if len(items)!=expected:raise ValueError(('count',len(items),expected))
 target=f'{REMOTE}/{cycle}'
 run(SSH+[f'test ! -e {shlex.quote(target)} && mkdir {shlex.quote(target)}'])
 transit=B/f'.transit_{cycle}'; transit.mkdir(exist_ok=False)
 try:
  for item in items:
   src=item['path'];basename=pathlib.Path(src).name
   if basename!=src.split('/')[-1] or not basename.startswith('step_'):raise ValueError(src)
   local_file=transit/basename
   download('/content/r234c_gc37_60b2bf75/'+src,local_file)
   if local_file.stat().st_size!=item['bytes'] or sha(local_file)!=item['sha256']:raise ValueError(('local_hash',src))
   run(SCP+[str(local_file),f'{HOST}:{target}/{basename}'])
   remote_sha=run(SSH+[f'sha256sum {shlex.quote(target+"/"+basename)}']).split()[0]
   if remote_sha!=item['sha256']:raise ValueError(('CRC_hash',src,remote_sha))
   local_file.unlink() # newly created transfer buffer only; verified durable source+destination retained
   print('RAW_CRC_VERIFIED',cycle,basename,item['bytes'],item['sha256'],flush=True)
  sums=transit/'SHA256SUMS'
  with sums.open('x') as f:
   for item in items:f.write(item['sha256']+'  '+pathlib.Path(item['path']).name+'\n')
  run(SCP+[str(sums),f'{HOST}:{target}/SHA256SUMS'])
  run(SCP+[str(local),f'{HOST}:{target}/RAW_MANIFEST.json'])
  print(run(SSH+[f'cd {shlex.quote(target)} && sha256sum -c SHA256SUMS']))
  print('RAW_CYCLE_DONE',cycle,flush=True)
 finally:
  # Preserve manifest and any incomplete transfer buffer on failure.
  pass
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('cycle');main(ap.parse_args().cycle)
