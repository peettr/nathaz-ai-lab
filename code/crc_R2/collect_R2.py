#!/usr/bin/env python3
"""Collect terminal R1 scores once, preserving raw grader JSON and §4-only feedback."""
from pathlib import Path
import json,hashlib,subprocess,csv,sys,re
D=Path(__file__).parent; S=D.parent
manifest=json.loads((D/'manifest.json').read_text())
sub=[json.loads(x) for x in (D/'submission.jsonl').read_text().splitlines()]
bytag={}
for ev in sub:bytag[(ev['model'],ev['id'])]=ev
assert len(bytag)==9
HOST='[邮箱]'
OPT=['-o','ControlPath=./.ssh/sockets/[邮箱]','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false']
def remote(command):
 p=subprocess.run(['ssh','-n',*OPT,HOST,command],capture_output=True,text=True,timeout=45)
 if p.returncode:raise RuntimeError(p.stderr+' '+p.stdout)
 return p.stdout

def excerpt(text,kind):
 lines=text.splitlines()
 if kind=='compile':return '\n'.join(lines[:200])
 marks=('Error','Exception','Traceback','FOAM FATAL','Floating point exception')
 first=next((i for i,s in enumerate(lines) if any(m in s for m in marks)),len(lines))
 return '\n'.join(lines[:50]+lines[first:][-150:])

allrows=[]
for r in manifest:
 model,ident,root=r['model'],r['id'],r['root']
 dest=S/model/ident/'grade_R2.json';fb=S/model/ident/'fb_R2.txt'
 ev=bytag[(model,ident)]
 state=remote(f'if test -f {root}/run.exitcode; then printf "EXIT="; cat {root}/run.exitcode; else echo PENDING; fi; if test -f {root}/grade.json; then sha256sum {root}/grade.json; fi')
 if 'PENDING' in state:
  allrows.append(dict(model=model,id=ident,status='pending',level='',标签='',是否需反馈=''))
  continue
 exitval=re.search(r'EXIT=(\d+)',state)
 digest=re.search(r'\b([0-9a-f]{64})\s+\S+/grade.json',state)
 if not digest:
  allrows.append(dict(model=model,id=ident,status='harness_fault_no_json',level='',标签='',是否需反馈='no'))
  print('MISSING_JSON',model,ident,state.strip());continue
 if not dest.exists():
  subprocess.run(['scp',*OPT,f'{HOST}:{root}/grade.json',str(dest)],check=True,stdout=subprocess.DEVNULL)
 assert hashlib.sha256(dest.read_bytes()).hexdigest()==digest.group(1), (model,ident,'hash mismatch')
 data=json.loads(dest.read_text())
 status=data.get('status');level=data.get('level');failure=data.get('failure')
 if status not in ('scored','L0','harness_fault'):raise ValueError((model,ident,status))
 if status=='L0':
  if not fb.exists():
   if r['task']=='T01':
    # Frozen grader already captured the exact original exception or stderr excerpt.
    text=data.get('feedback','')
   else:
    err=data.get('error','')
    steps=data.get('steps',{})
    work=root+'/solver_work/'
    if steps.get('compile') not in (None,0) or 'compile' in err.lower() or 'Make/' in err:
     raw=remote(f'if test -f {work}compile.log; then cat {work}compile.log; else cat {root}/grade.log; fi')
     text=excerpt(raw,'compile') or err
    elif steps.get('pimpleFoam')=='timeout' or 'exceeded 4h' in err:
     text='TimeoutError: pimpleFoam exceeded 4h'
    else:
     stage=next((x for x,v in steps.items() if v not in (0,None)),None)
     log=(work+stage+'.log') if stage else root+'/grade.log'
     raw=remote(f'if test -f {log}; then cat {log}; else cat {root}/grade.log; fi')
     text=excerpt(raw,'runtime') or err
   fb.write_text(text.rstrip('\n')+'\n')
 elif fb.exists():raise AssertionError(('stale feedback',model,ident))
 tags=[]
 if data.get('fluctuation_statistics_not_rotated_signature'):tags.append('脉动统计未随风向转')
 if r['task']=='T01' and status=='scored' and any(x.get('quasisteady_shortcut') for x in data.get('cases',{}).values()):tags.append('准静态捷径')
 if r['task']=='T03' and status=='scored' and level=='L2':
  rows=data.get('primary_by_height',{}).values()
  if all(x['direction_abs_error_deg']<=1.5 and x['mean_speed_abs_relative_error']<=.03 and x['rho_offdiagonal_max_abs_delta']<=.03 and x['R_diagonal_max_abs_relative_error']<=.1 for x in rows) and any(.05<x['R_diagonal_max_abs_relative_error']<=.1 for x in rows):tags.append('对角边界')
 allrows.append(dict(model=model,id=ident,status=status,level=level or '',标签=';'.join(tags),是否需反馈='yes' if status=='L0' else 'no'))
 print('COLLECTED',model,ident,ev['job'],exitval.group(1) if exitval else '?',status,level,flush=True)
with (D/'summary_R2.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['model','id','status','level','标签','是否需反馈']);w.writeheader();w.writerows(allrows)
assert len(allrows)==9
from collections import Counter
print('SUMMARY',Counter(x['status'] for x in allrows),flush=True)
