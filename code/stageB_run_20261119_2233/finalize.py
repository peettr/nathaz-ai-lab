#!/usr/bin/env python3
"""Read back exact six host-verified case JSONs and run frozen classifier offline."""
import json,hashlib,pathlib,sys
from assert_T17 import evaluate
R=pathlib.Path(__file__).resolve().parent
labels=('t15_s1','t15_s2','t4_s1','t4_s2','bounce_s1','bounce_s2')
sessions=[d for d in R.glob('session_*') if (d/'evidence/run.done').is_file()]
if len(sessions)!=1:raise RuntimeError(f'expect one completed session, got {sessions}')
e=sessions[0]/'evidence';cases={g:{} for g in ('bounce','t4','t15')}
for label in labels:
 p=e/(label+'_case.json');h=hashlib.sha256(p.read_bytes()).hexdigest()
 if h!=(e/(p.name+'.sha256')).read_text().strip():raise RuntimeError('case SHA '+label)
 g,s=label.split('_s');cases[g][s]=json.loads(p.read_text())
done=json.loads((e/'run.done').read_text());assert done['verified']==list(labels)
for p in e.glob('*.sha256'):
 q=p.with_name(p.name[:-7]);assert hashlib.sha256(q.read_bytes()).hexdigest()==p.read_text().strip(),q
inp={'schema':'T17-B-v1','cases':cases};(R/'input_all.json').write_text(json.dumps(inp,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
result=evaluate(inp);(R/'T17_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print(json.dumps({'verdicts':result['group_verdicts'],'pairs':{k:v['verdict'] for k,v in result['pairwise'].items()},'case_E':result['case_E_link']},ensure_ascii=False))
