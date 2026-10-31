#!/usr/bin/env python3
"""Submit each preflighted R2 root exactly once, register immediately."""
import json,re,subprocess,os
from pathlib import Path
D=Path(__file__).parent; rows=json.loads((D/'manifest.json').read_text())
HOST='[邮箱]'
OPT=['-o','ControlPath=./.ssh/sockets/[邮箱]','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false']
CTX=os.environ['RC_CTX']; ledger=D/'submission.jsonl'
assert len(rows)==9 and all((D/(r['model']+'_'+r['id']+'.preflight.txt')).exists() for r in rows)
assert (D/'EXPERIMENT_CARD.md').exists()
prior=[json.loads(x) for x in ledger.read_text().splitlines()] if ledger.exists() else []
seen={r['model']+'_'+r['id'] for r in prior}
for r in rows:
 root=r['root'];tag=r['model']+'_'+r['id'];script=Path(r['run_script']).name
 if tag in seen:
  print('ALREADY_SUBMITTED_NO_RETRY',tag,flush=True);continue
 # The only remote action here is literal cd followed by one qsub; all preflight was a separate call.
 p=subprocess.run(['ssh','-n',*OPT,HOST,f'cd {root} && qsub ./{script}'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=60)
 if p.returncode:raise RuntimeError(f'{tag} submission failed rc={p.returncode}: {p.stdout} {p.stderr}; STOP, no retry')
 match=re.search(r'Your job (\d+)\b',p.stdout+'\n'+p.stderr)
 if not match:raise RuntimeError(f'{tag} unknown receipt: {p.stdout} {p.stderr}; STOP, no retry')
 job=match.group(1)
 event=dict(model=r['model'],id=r['id'],job=job,root=root,receipt=p.stdout.strip(),registration=None)
 with ledger.open('a') as f:f.write(json.dumps(event,ensure_ascii=False)+'\n');f.flush()
 print('SUBMITTED',tag,job,flush=True)
 args=['rc-job','--ctx',CTX,'--cluster','crc','--job',job,'--title',f'L22.6 R2 {tag}','--eta','10h','--log',root+'/solver_work/pimpleFoam.log','--exit-file',root+'/run.exitcode','--root',root,'--card',str(D/'EXPERIMENT_CARD.md'),'--code','openfoam','--end','120']
 q=subprocess.run(args,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=60)
 if q.returncode:raise RuntimeError(f'{tag} submitted job {job} registration failed: {q.stdout} {q.stderr}; STOP')
 event['registration']=(q.stdout+'\n'+q.stderr).strip()
 with ledger.open('a') as f:f.write(json.dumps(event,ensure_ascii=False)+'\n');f.flush()
 print('REGISTERED',tag,job,event['registration'][:180],flush=True)
print('ALL_SUBMITTED_REGISTERED',len(rows),flush=True)
