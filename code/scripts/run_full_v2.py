#!/usr/bin/env python3
"""Full A1 v2 launch; blocked unless Lead explicitly releases ticket 0069 gate."""
import argparse,hashlib,os,subprocess,time
from pathlib import Path
ROOT=Path('./ftkb_figures/full_v2');S='./22_Lab/06_Logs/figure_kb/scripts'
HOST='[邮箱]';SOCK='~/.ssh/sockets/[邮箱]'
SSH=['ssh','-o',f'ControlPath={SOCK}','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false'];PY='./services/ftkb/.venv/bin/python'
def run(args):subprocess.run(args,stdin=subprocess.DEVNULL,check=True)
def ssh(cmd):run(SSH+['-n',HOST,cmd])
def checksum(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--lead-go',action='store_true');a=p.parse_args()
 if not a.lead_go:raise SystemExit('STOP: 0069 completion and explicit Lead full-run go required')
 run(SSH+['-O','check',HOST]);ROOT.mkdir(parents=True,exist_ok=True)
 ssh('mkdir -p ~/ftkb_figures/full_v2')
 # Pilot output is never seeded into this root; run all docs once into new paths.
 ssh('nice -n 19 ~/ftkb_text/venv/bin/python ~/ftkb_figures/scripts/figure_pipeline_v2.py --source desktop --root ~/ftkb_figures/full_v2 --db ~/ftkb_figures/full_v2/desktop.sqlite --all-figures >> ~/ftkb_figures/full_v2/run.log 2>&1')
 local=ROOT/'local.sqlite'
 with open(ROOT/'run.log','a') as log:
  proc=subprocess.Popen(['nice','-n','19',PY,S+'/figure_pipeline_v2.py','--source','local','--root',str(ROOT),'--db',str(local),'--all-figures'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
  while proc.poll() is None:
   time.sleep(30)
   run(['python3',S+'/sync_thumbs_v2.py','--db',str(local),'--root',str(ROOT),'--remote-root','full_v2','--batch','500'])
  if proc.returncode:raise RuntimeError(f'local extraction failed {proc.returncode}')
 run(['python3',S+'/sync_thumbs_v2.py','--db',str(local),'--root',str(ROOT),'--remote-root','full_v2','--batch','500'])
 ssh('test -f ~/ftkb_figures/full_v2/compact.sqlite || ~/ftkb_text/venv/bin/python ~/ftkb_figures/scripts/compact_one.py --source ~/ftkb_figures/full_v2/desktop.sqlite --out ~/ftkb_figures/full_v2/compact.sqlite')
 compact=ROOT/'desktop_compact.sqlite'
 if compact.exists():raise FileExistsError(compact)
 run(['scp']+SSH[1:]+[HOST+':ftkb_figures/full_v2/compact.sqlite',str(compact)])
 remote=subprocess.check_output(SSH+['-n',HOST,'sha256sum ~/ftkb_figures/full_v2/compact.sqlite'],stdin=subprocess.DEVNULL,text=True).split()[0]
 if checksum(compact)!=remote:raise RuntimeError('desktop DB checksum mismatch')
 out=ROOT/'figures_full_v2.sqlite'
 run([PY,S+'/merge_full.py','--desktop',str(compact),'--local',str(local),'--out',str(out)])
 run(['env','OPENBLAS_NUM_THREADS=1',PY,S+'/build_vectors_v2.py','--db',str(out),'--out',str(ROOT/'vectors_full_v2')])
 for suffix in ('.npy','.json'):
  file=ROOT/('vectors_full_v2'+suffix)
  run(['scp']+SSH[1:]+[str(file),HOST+':ftkb_figures/full_v2/'+file.name])
  remote=subprocess.check_output(SSH+['-n',HOST,'sha256sum ~/ftkb_figures/full_v2/'+file.name],stdin=subprocess.DEVNULL,text=True).split()[0]
  if checksum(file)!=remote:raise RuntimeError('vector checksum mismatch '+suffix)
 print('complete',out,out.stat().st_size,ROOT/'vectors_full_v2.npy')
if __name__=='__main__':main()
