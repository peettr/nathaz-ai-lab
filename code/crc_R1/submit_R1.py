#!/usr/bin/env python3
"""One qsub per new root, immediately register; never retry a submission."""
import csv,json,re,subprocess,sys,os
from pathlib import Path
D=Path(__file__).parent
rows=json.loads((D/'manifest.json').read_text()); host='[邮箱]'
opt=['-o','ControlPath=./.ssh/sockets/[邮箱]','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false']
CTX=os.environ['RC_CTX']
ledger=D/'submission.jsonl'
existing=[json.loads(x) for x in ledger.read_text().splitlines()] if ledger.exists() else []
# The first submitted job was registered separately after rc-job required a custom pattern.
assert existing and existing[0]['job']=='1619254' and existing[0]['registration'] is None
assert len(rows)==24 and all((D/(r['model']+'_'+r['id']+'.preflight.txt')).exists() for r in rows)
for r in rows:
 root=r['root']; tag=r['model']+'_'+r['id']; script=Path(r['run_script']).name
 if tag=='gpt_T01_W_r1':
  print('ALREADY_SUBMITTED_REGISTERED',tag,'1619254',flush=True)
  continue
 # The SSH remote command is only literal cd and one qsub. Preflight was completed in an earlier tool call.
 p=subprocess.run(['ssh','-n',*opt,host,f'cd {root} && qsub ./{script}'],capture_output=True,text=True,timeout=45)
 if p.returncode:raise RuntimeError(f'{tag} submission failed rc={p.returncode}: {p.stdout} {p.stderr}; STOP, no retry')
 m=re.search(r'Your job (\d+)\b',p.stdout+'\n'+p.stderr)
 if not m:raise RuntimeError(f'{tag} unknown job receipt: {p.stdout} {p.stderr}; STOP')
 job=m.group(1)
 event={'model':r['model'],'id':r['id'],'job':job,'root':root,'receipt':p.stdout.strip(),'registration':None}
 with ledger.open('a') as f:f.write(json.dumps(event)+'\n');f.flush()
 print('SUBMITTED',tag,job,flush=True)
 args=['rc-job','--ctx',CTX,'--cluster','crc','--job',job,'--title',f'L22.6 R1 {tag}', '--eta','10h' if r['task']=='T03' else '3h',
       '--log',root+'/scheduler.log' if r['task']=='T01' else root+'/solver_work/pimpleFoam.log','--exit-file',root+'/run.exitcode','--root',root,
       '--card',str(D/'EXPERIMENT_CARD.md')]
 if r['task']=='T03':args+=['--code','openfoam','--end','120']
 else:args+=['--code','custom','--pattern','Progress: ([0-9]+)']
 q=subprocess.run(args,capture_output=True,text=True,timeout=45)
 if q.returncode:raise RuntimeError(f'{tag} job {job} submitted but registration failed: {q.stdout} {q.stderr}; STOP')
 event['registration']=(q.stdout+'\n'+q.stderr).strip()
 with ledger.open('a') as f:f.write(json.dumps(event,ensure_ascii=False)+'\n');f.flush()
 print('REGISTERED',tag,job,event['registration'][:200],flush=True)
print('ALL_SUBMITTED_REGISTERED',len(rows),flush=True)
