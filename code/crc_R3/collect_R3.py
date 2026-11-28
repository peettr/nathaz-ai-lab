#!/usr/bin/env python3
"""Collect six terminal R3 grader outputs without generating feedback."""
from pathlib import Path
import json,hashlib,subprocess,csv,re
from collections import Counter
D=Path(__file__).parent; S=D.parent
manifest=json.loads((D/'manifest.json').read_text())
sub=[json.loads(x) for x in (D/'submission.jsonl').read_text().splitlines()]
bytag={(e['model'],e['id']):e for e in sub}
assert len(manifest)==len(bytag)==6
HOST='[邮箱]'
OPT=['-o','ControlPath=./.ssh/sockets/[邮箱]','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false']
def remote(command):
 p=subprocess.run(['ssh','-n',*OPT,HOST,command],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45)
 if p.returncode:raise RuntimeError(p.stderr+' '+p.stdout)
 return p.stdout
rows=[]
for r in manifest:
 model,ident,root=r['model'],r['id'],r['root']
 dest=S/model/ident/'grade_R3.json'; ev=bytag[(model,ident)]
 state=remote(f'if test -f {root}/run.exitcode; then printf "EXIT="; cat {root}/run.exitcode; else echo PENDING; fi; if test -f {root}/grade.json; then sha256sum {root}/grade.json; fi')
 if 'PENDING' in state:
  rows.append(dict(model=model,id=ident,status='pending',level='',标签=''))
  continue
 exitval=re.search(r'EXIT=(\d+)',state)
 digest=re.search(r'\b([0-9a-f]{64})\s+\S+/grade.json',state)
 if not digest:
  rows.append(dict(model=model,id=ident,status='harness_fault_no_json',level='',标签=''))
  print('MISSING_JSON',model,ident,state.strip(),flush=True);continue
 if not dest.exists():
  subprocess.run(['scp',*OPT,f'{HOST}:{root}/grade.json',str(dest)],stdin=subprocess.DEVNULL,check=True,stdout=subprocess.DEVNULL)
 assert hashlib.sha256(dest.read_bytes()).hexdigest()==digest.group(1),(model,ident,'hash mismatch')
 data=json.loads(dest.read_text());status=data.get('status');level=data.get('level')
 if status not in ('scored','L0','harness_fault'):raise ValueError((model,ident,status))
 tags=[]
 if data.get('fluctuation_statistics_not_rotated_signature'):tags.append('脉动统计未随风向转')
 if status=='scored' and level=='L2':
  h=list(data.get('primary_by_height',{}).values())
  if h and all(x['direction_abs_error_deg']<=1.5 and x['mean_speed_abs_relative_error']<=.03 and x['rho_offdiagonal_max_abs_delta']<=.03 and x['R_diagonal_max_abs_relative_error']<=.1 for x in h) and any(.05<x['R_diagonal_max_abs_relative_error']<=.1 for x in h):tags.append('对角边界')
 rows.append(dict(model=model,id=ident,status=status,level=level or '',标签=';'.join(tags)))
 print('COLLECTED',model,ident,ev['job'],exitval.group(1) if exitval else '?',status,level,flush=True)
with (D/'summary_R3.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['model','id','status','level','标签']);w.writeheader();w.writerows(rows)
assert len(rows)==6
print('SUMMARY',Counter(x['status'] for x in rows),flush=True)
