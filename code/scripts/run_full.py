#!/usr/bin/env python3
"""A1 full-run driver. DO NOT invoke before 0069 completion and Lead go-ahead."""
import argparse,hashlib,os,subprocess,time
from pathlib import Path
ROOT=Path('./ftkb_figures'); S='./22_Lab/06_Logs/figure_kb/scripts'
HOST='[邮箱]'; SOCK='~/.ssh/sockets/[邮箱]'
SSH=['ssh','-o',f'ControlPath={SOCK}','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false'];
REMOTE='~/ftkb_figures';PY='./services/ftkb/.venv/bin/python'
def run(args):subprocess.run(args,check=True,stdin=subprocess.DEVNULL)
def ssh(command):run(SSH+['-n',HOST,command])
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--lead-go',action='store_true',help='Lead confirms 0069 complete and explicitly says full go');a=p.parse_args()
 if not a.lead_go:raise SystemExit('STOP: full extraction requires explicit Lead go after ticket 0069')
 run(SSH+['-O','check',HOST])
 local=ROOT/'full_local.sqlite';remote='~/ftkb_figures/full_desktop.sqlite'
 if not local.exists():run([PY,S+'/seed_pilot.py','--pilot',str(ROOT/'pilot/local.sqlite'),'--full',str(local)])
 ssh('test -f ~/ftkb_figures/full_desktop.sqlite || ~/ftkb_text/venv/bin/python ~/ftkb_figures/scripts/seed_pilot.py --pilot ~/ftkb_figures/pilot/desktop.sqlite --full ~/ftkb_figures/full_desktop.sqlite')
 # One remote worker; no SSH input stream, no cluster allocation.
 ssh('nice -n 19 ~/ftkb_text/venv/bin/python ~/ftkb_figures/scripts/figure_pipeline.py --source desktop --root ~/ftkb_figures --db ~/ftkb_figures/full_desktop.sqlite --all-figures > ~/ftkb_figures/full_desktop.log 2>&1')
 # One 工作站 extraction worker; transfer completed PDFs' thumbnails in verified batches of <=500.
 with open(ROOT/'full_local.log','a') as log:
  proc=subprocess.Popen(['nice','-n','19',PY,S+'/figure_pipeline.py','--source','local','--root',str(ROOT),'--db',str(local),'--all-figures'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
  while proc.poll() is None:
   time.sleep(30)
   run(['nice','-n','19','python3',S+'/sync_thumbs.py','--db',str(local),'--root',str(ROOT),'--batch','500'])
  if proc.returncode:raise RuntimeError(f'local extractor failed exit={proc.returncode}; see {ROOT}/full_local.log')
 run(['python3',S+'/sync_thumbs.py','--db',str(local),'--root',str(ROOT),'--batch','500'])
 ssh('test -f ~/ftkb_figures/full_desktop_compact.sqlite || ~/ftkb_text/venv/bin/python ~/ftkb_figures/scripts/compact_one.py --source ~/ftkb_figures/full_desktop.sqlite --out ~/ftkb_figures/full_desktop_compact.sqlite')
 dest=ROOT/'full_desktop_compact.sqlite'
 if dest.exists():raise FileExistsError(dest)
 run(['scp']+SSH[1:]+[HOST+':ftkb_figures/full_desktop_compact.sqlite',str(dest)])
 remote_hash=subprocess.check_output(SSH+['-n',HOST,'sha256sum ~/ftkb_figures/full_desktop_compact.sqlite'],stdin=subprocess.DEVNULL,text=True).split()[0]
 if digest(dest)!=remote_hash:raise RuntimeError('remote SQLite SHA256 mismatch')
 out=ROOT/'figures_full.sqlite'
 if out.exists():raise FileExistsError(out)
 run([PY,S+'/merge_full.py','--desktop',str(dest),'--local',str(local),'--out',str(out)])
 print('full output:',out,'bytes:',out.stat().st_size,'sha256:',digest(out))
if __name__=='__main__':main()
