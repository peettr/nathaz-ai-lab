#!/usr/bin/env python3
"""Prepare a fresh G1 coarse retry; never mutate prior solve roots."""
from pathlib import Path
import shutil
import hashlib
base=Path(__file__).parent
src=base/'solve_v3/cases/coarse/g1_driver.py'
out=base/'solve_relax'
assert not out.exists(), 'fresh output only'
out.mkdir()
s=src.read_text()
assert "'solverName':'DASimpleFoam','primalMinResTol'" in s
s=s.replace("'solverName':'DASimpleFoam','primalMinResTol'", "'solverName':'DASimpleFoam','printInterval':1,'primalMinResTol'",1)
a=s.index('def roof_trace():')
b=s.index('\ndef residuals():',a)
s=s[:a]+'''def roof_trace():
 # DASimpleFoam calls calcAllFunctions each iteration (source lines 162-163);
 # printInterval=1 prints roofCp on rank 0. Do not use controlDict functionObjects.
 txt=(case/'g1_rank0.log').read_text(errors='replace')
 values=[float(v) for v in re.findall(r'^\\s*roofCp:\\s*([+-]?(?:\\d+\\.?\\d*|\\.\\d+)(?:[eE][+-]?\\d+)?)',txt,re.M)]
 if not values:raise RuntimeError('DAFoam rank0 roofCp trace absent')
 if not all(math.isfinite(v) for v in values):raise RuntimeError('nonfinite roofCp')
 with (case/'g1_cp_trace.csv').open('w') as f:
  f.write('iteration,roof_mean_cp\\n')
  for i,v in enumerate(values,1):f.write(f'{i},{v:.15g}\\n')
 return list(enumerate(values,1))
''' + s[b:]
a=s.index('if comm.rank==0:\n trace=roof_trace()')
b=s.index('if not gate:\n',a)
s=s[:a]+'''if comm.rank==0:
 try:
  trace=roof_trace(); res=residuals(); fields=['Ux','Uy','Uz','p','k','omega']
  enough=all(len(res.get(f,[]))>=500 for f in fields) and len(trace)>=500
  ratios={f:res[f][-1]/res[f][0] for f in fields} if enough else {}
  cp_delta=abs(trace[-1][1]-trace[-500][1])/max(abs(trace[-500][1]),1e-6) if enough else None
  gate=bool(enough and all(math.isfinite(v) and v<=1e-4 for v in ratios.values()) and cp_delta<.005)
  result={'source':'DAFoam v5.1.1 rank0 printInterval=1','cells':n,'u_ref':u_ref,'steps_by_field':{f:len(res.get(f,[])) for f in fields},'roof_samples':len(trace),'residual_ratios':ratios,'cp_last500_change':cp_delta,'primal_gate':gate,'baseline_cp':base}
  (case/'g1_gate.json').write_text(json.dumps(result,indent=2)+'\\n')
  decision=(gate,None)
 except Exception as exc:
  (case/'g1_gate_error.txt').write_text(repr(exc)+'\\n')
  decision=(False,repr(exc))
else:decision=None
try:
 decision=comm.bcast(decision,root=0)
except Exception:
 comm.Abort(87)
if decision[1] is not None:
 comm.Abort(88)
gate=decision[0]
''' + s[b:]
# A rank-zero failure in any later gate must not strand other ranks at bcast.
s=s.replace("true=[float(v) for v in re.findall", "true=[float(v) for v in re.findall")
(out/'g1_driver.py').write_text(s)
sol=(base/'solve_v3/cases/coarse/system/fvSolution').read_text()
assert 'p 0.3;' in sol and '0.7;' in sol
sol=sol.replace('p 0.3;','p 0.2;').replace('0.7;','0.5;')
(out/'fvSolution').write_text(sol)
for p in (out/'g1_driver.py',out/'fvSolution'):
 print(p,hashlib.sha256(p.read_bytes()).hexdigest())
