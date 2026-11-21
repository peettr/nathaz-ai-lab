#!/usr/bin/env python3
"""G1 fail-closed primal/adjoint/FD; source: DAFoam v5.1.1.
Rank 0 C++ stdout is spooled by the launcher; this file never decides a pass
from the process exit or from a PETSc denormal residual alone.
"""
import json, math, os, re, sys, time
from pathlib import Path
import numpy as np
from mpi4py import MPI
from petsc4py import PETSc
import openmdao.api as om
from mphys.core import Multipoint
from mphys.scenarios import ScenarioAerodynamic
from dafoam.mphys import DAFoamBuilder
comm=MPI.COMM_WORLD
# Fail-fast on ANY uncaught rank exception, not only the primary gate. Otherwise
# sibling ranks can block forever at the next collective.
def _abort_on_exception(kind, value, tb):
 sys.__excepthook__(kind, value, tb)
 try:comm.Abort(89)
 except Exception:pass
sys.excepthook=_abort_on_exception
case=Path.cwd(); sample=json.loads((case/'sample_cells.json').read_text())
ids=sample['cell_ids']; n=sample['mesh_cells']
assert len(ids)==5 and len(set(ids))==5 and all(0<=i<n for i in ids)
empty=json.loads((case/'empty_reference.json').read_text())
u_ref=float(empty['U_at_H']);assert 0<u_ref<30
PETSc.Options().setValue('ksp_monitor_true_residual','')
PETSc.Options().setValue('ksp_converged_reason','')
opts={
 'solverName':'DASimpleFoam','printInterval':1,'primalMinResTol':1e-12,'primalMinResTolDiff':1e20,
 'primalBC':{'useWallFunction':True},
 'function':{'roofCp':{'type':'patchMean','source':'patchToFace','patches':['roof'],'varName':'p','varType':'scalar','index':0,'scale':2.0/u_ref**2}},
 'adjEqnOption':{'gmresRelTol':1e-6,'gmresMaxIters':2000,'gmresRestart':200,'pcFillLevel':1,'jacMatReOrdering':'rcm'},
 'normalizeStates':{'U':10.,'p':u_ref*u_ref/2,'nut':0.1,'phi':1.,'k':0.5,'omega':5.},
 'inputInfo':{'beta':{'type':'field','fieldName':'betaFIOmega','fieldType':'scalar','distributed':False,'components':['solver','function']}},
}
class Top(Multipoint):
 def setup(self):
    builder=DAFoamBuilder(options=opts,mesh_options=None,scenario='aerodynamic');builder.initialize(self.comm)
    self.add_subsystem('dvs',om.IndepVarComp(),promotes=['*'])
    self.mphys_add_scenario('scenario1',ScenarioAerodynamic(aero_builder=builder))
 def configure(self):
    self.dvs.add_output('beta',val=np.ones(n),distributed=False)
    self.connect('beta','scenario1.beta');self.add_design_var('beta',lower=.2,upper=5.)
    self.add_objective('scenario1.aero_post.roofCp')
prob=om.Problem(model=Top());prob.setup(mode='rev')
name='scenario1.aero_post.roofCp'; beta=np.ones(n)

def status(label,payload):
 if comm.rank==0:
    target=case/'g1_progress.jsonl'
    with target.open('a') as f:f.write(json.dumps({'phase':label,'at':time.time(),**payload})+'\n');f.flush();os.fsync(f.fileno())
 comm.Barrier()

def primal(tag):
 prob.set_val('beta',beta)
 t=time.monotonic();prob.run_model();comm.Barrier()
 value=float(np.asarray(prob.get_val(name)).ravel()[0]); seconds=time.monotonic()-t
 status(tag,{'seconds':seconds,'cp':value})
 return value

# The launcher records rank-zero C++ logs in g1_rank0.log. For an independent
# gate the postProcessing roofMean trace and the C++ residual series are required.
def roof_trace():
 # DASimpleFoam calls calcAllFunctions each iteration (source lines 162-163);
 # printInterval=1 prints roofCp on rank 0. Do not use controlDict functionObjects.
 txt=(case/'g1_rank0.log').read_text(errors='replace')
 values=[float(v) for v in re.findall(r'^\s*roofCp:\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)',txt,re.M)]
 if not values:raise RuntimeError('DAFoam rank0 roofCp trace absent')
 if not all(math.isfinite(v) for v in values):raise RuntimeError('nonfinite roofCp')
 with (case/'g1_cp_trace.csv').open('w') as f:
  f.write('iteration,roof_mean_cp\n')
  for i,v in enumerate(values,1):f.write(f'{i},{v:.15g}\n')
 return list(enumerate(values,1))

def residuals():
 txt=(case/'g1_rank0.log').read_text(errors='replace')
 out={}
 for field,init in re.findall(r'Solving for\s+([A-Za-z][A-Za-z0-9]*),\s+Initial residual\s*=\s*([0-9.eE+-]+)',txt):
    v=float(init)
    if math.isfinite(v):out.setdefault(field,[]).append(v)
 return out

base=primal('baseline')
if comm.rank==0:
 try:
  trace=roof_trace(); res=residuals(); fields=['Ux','Uy','Uz','p','k','omega']
  enough=all(len(res.get(f,[]))>=500 for f in fields) and len(trace)>=500
  ratios={f:res[f][-1]/res[f][0] for f in fields} if enough else {}
  cp_delta=abs(trace[-1][1]-trace[-500][1])/max(abs(trace[-500][1]),1e-6) if enough else None
  gate=bool(enough and all(math.isfinite(v) and v<=1e-4 for v in ratios.values()) and cp_delta<.005)
  result={'source':'DAFoam v5.1.1 rank0 printInterval=1','cells':n,'u_ref':u_ref,'steps_by_field':{f:len(res.get(f,[])) for f in fields},'roof_samples':len(trace),'residual_ratios':ratios,'cp_last500_change':cp_delta,'primal_gate':gate,'baseline_cp':base}
  (case/'g1_gate.json').write_text(json.dumps(result,indent=2)+'\n')
  decision=(gate,None)
 except Exception as exc:
  (case/'g1_gate_error.txt').write_text(repr(exc)+'\n')
  decision=(False,repr(exc))
else:decision=None
try:
 decision=comm.bcast(decision,root=0)
except Exception:
 comm.Abort(87)
if decision[1] is not None:
 comm.Abort(88)
gate=decision[0]
if not gate:
 status('PRIMAL_GATE_FAILED',{});sys.exit(41)
status('ADJOINT_START',{})
t=time.monotonic();totals=prob.compute_totals(of=[name],wrt=['beta']);comm.Barrier()
grad=np.asarray(next(iter(totals.values()))).ravel();assert len(grad)==n
status('ADJOINT_END',{'seconds':time.monotonic()-t})
if comm.rank==0:
 txt=(case/'g1_rank0.log').read_text(errors='replace')
 true=[float(v) for v in re.findall(r'true resid norm\s+([0-9.eE+-]+)',txt,re.I)]
 adj_gate=(len(true)>=2 and true[0]>0 and all(math.isfinite(x) and x>1e-290 for x in true) and true[-1]/true[0]<1e-6 and 'CONVERGED_' in txt)
 with (case/'g1_adjoint_gate.json').open('w') as f:json.dump({'true_residuals':true,'relative':true[-1]/true[0] if true and true[0] else None,'adjoint_gate':adj_gate},f)
else:adj_gate=None
adj_gate=comm.bcast(adj_gate,root=0)
if not adj_gate:
 status('ADJOINT_GATE_FAILED',{});sys.exit(42)
results=[]
# Predeclare FD endpoint noise gate: each endpoint begins with the same beta=1
# state, uses the fixed 5000-iteration solver cap and must end at least 100x
# below the baseline terminal residual in every field. If pyDAFoam does not
# restore a common state, the recorded end-point evidence is insufficient.
if comm.rank==0:
 baseline_terminal={f:res[f][-1] for f in fields}
else:baseline_terminal=None
baseline_terminal=comm.bcast(baseline_terminal,root=0)
for eps in (1e-3,1e-2,1e-4):
 for i in ids:
    endpoints=[]
    for sign in (1,-1):
     before=residuals() if comm.rank==0 else None
     beta[i]=1+sign*eps
     value=primal(f'{"plus" if sign==1 else "minus"}_{eps}_{i}')
     if comm.rank==0:
      after=residuals()
      start={f:len(before.get(f,[])) for f in fields}
      fresh={f:after.get(f,[])[start[f]:] for f in fields}
      verified=all(len(v)>0 and v[-1]<=baseline_terminal[f]*1e-2 for f,v in fresh.items())
      endpoint={'cell':i,'step':eps,'sign':sign,'cp':value,'residual_samples':{f:len(v) for f,v in fresh.items()},'end_residuals':{f:v[-1] if v else None for f,v in fresh.items()},'deep_gate':verified}
     else:endpoint=None
     endpoint=comm.bcast(endpoint,root=0)
     endpoints.append(endpoint)
     status('FD_ENDPOINT',endpoint)
     if not endpoint['deep_gate']:
      status('FD_NOISE_GATE_FAILED',endpoint);sys.exit(43)
    beta[i]=1
    plus,minus=(v['cp'] for v in endpoints)
    fd=(plus-minus)/(2*eps);a=float(grad[i]);denom=max(abs(fd),abs(a))
    rel=abs(fd-a)/denom if denom>=1e-12 else None
    results.append({'cell':i,'step':eps,'plus':plus,'minus':minus,'fd':fd,'adjoint':a,'relative_error':rel})
    status('FD',results[-1])
if comm.rank==0:(case/'g1_fd.json').write_text(json.dumps(results,indent=2)+'\n')
status('COMPLETE',{})
