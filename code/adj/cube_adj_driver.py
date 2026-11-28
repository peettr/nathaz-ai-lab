#!/usr/bin/env python3
"""Cube D (6000) or selected F fallback (3000); fixed cold state per branch."""
import json, math, os, re, sys, time, types
from pathlib import Path
import numpy as np
from mpi4py import MPI
from petsc4py import PETSc
import openmdao.api as om
from mphys.core import Multipoint
from mphys.scenarios import ScenarioAerodynamic
from dafoam.mphys import DAFoamBuilder

comm=MPI.COMM_WORLD

def abort(kind,value,tb):
    sys.__excepthook__(kind,value,tb)
    comm.Abort(89)
sys.excepthook=abort
case=Path.cwd(); sample=json.loads((case/'sample_cells.json').read_text())
n=sample['mesh_cells']; ids=sample['cell_ids']
arm=(case/'branch').read_text().strip()
steps=int((case/'expected_steps').read_text())
assert (arm,n,steps) in [('D',227656,6000),('F',195656,3000)]
import subprocess
def persist(*files):
 if comm.rank==0:
  subprocess.run(['python',str(case.parent/'return_cube.py'),arm,*[str(case/f) for f in files]],check=True)
 comm.Barrier()
u_ref=1.0 # D/F log-law inlet reference U(H) retained from 1769443
PETSc.Options().setValue('ksp_monitor_true_residual','')
PETSc.Options().setValue('ksp_converged_reason','')
opts={
 'solverName':'DASimpleFoam','printInterval':1,'primalMinResTol':1e-12,'primalMinResTolDiff':1e20,
 'primalBC':{'useWallFunction':True},
 'function':{'roofCp':{'type':'patchMean','source':'patchToFace','patches':['roof'],'varName':'p','varType':'scalar','index':0,'scale':2.0/u_ref**2}},
 'adjEqnOption':{'gmresRelTol':1e-6,'gmresMaxIters':2000,'gmresRestart':int(os.environ.get('C2A_GMRES_RESTART','200')),'pcFillLevel':int(os.environ.get('C2A_PC_FILL','1')),'jacMatReOrdering':'rcm'},
 'normalizeStates':{'U':10.,'p':u_ref*u_ref/2,'nut':0.1,'phi':1.,'nuTilda':0.1},
 'inputInfo':{'beta':{'type':'field','fieldName':'betaFINuTilda','fieldType':'scalar','distributed':False,'components':['solver','function']}},
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

# Wrap the actual OpenMDAO adjoint solve: compute an independent matrix-vector
# product using its matrix-free PETSc operator and the actual RHS, not KSP history.
solver=prob.model.scenario1.coupling.solver
original_solve_linear=solver.solve_linear

def audited_solve_linear(self,d_outputs,d_residuals,mode):
    rhs=self.DASolver.array2Vec(d_outputs[self.stateName].copy())
    t=time.monotonic()
    original_solve_linear(d_outputs,d_residuals,mode)
    if mode!='rev':return
    ksp=self.DASolver.ksp
    A=ksp.getOperators()[0]
    applied=rhs.duplicate(); A.mult(self.psi,applied); applied.axpy(-1.,rhs)
    rnorm=applied.norm(); bnorm=rhs.norm(); ratio=rnorm/bnorm if bnorm else float('nan')
    if comm.rank==0:
        (case/'c2a_true_residual.json').write_text(json.dumps({'independent_Apsi_minus_b_over_b':ratio,'rhs_norm':bnorm,'residual_norm':rnorm,'gmres_iterations':ksp.getIterationNumber(),'ksp_reason':str(ksp.getConvergedReason()),'solve_seconds':time.monotonic()-t},indent=2)+'\n')
    applied.destroy();rhs.destroy()
solver.solve_linear=types.MethodType(audited_solve_linear,solver)

def status(phase,**data):
 if comm.rank==0:
    with (case/'g1_progress.jsonl').open('a') as f:
        f.write(json.dumps({'phase':phase,'at':time.time(),**data})+'\n');f.flush();os.fsync(f.fileno())
 comm.Barrier()

def logtext():return (case/'g1_rank0.log').read_text(errors='replace')

def residuals(txt):
 out={}
 for key,val in re.findall(r'Solving for\s+([A-Za-z][A-Za-z0-9]*),\s+Initial residual\s*=\s*([0-9.eE+-]+)',txt):
    v=float(val)
    if math.isfinite(v):out.setdefault(key,[]).append(v)
 assert len(out['p'])==3*len(out['Ux']),'p corrector count mismatch'
 out['p']=out['p'][0::3]
 return out

def cp_trace(txt):
 v=[float(x) for x in re.findall(r'^\s*roofCp:\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)',txt,re.M)]
 assert len(v)>=500 and all(math.isfinite(x) for x in v)
 return v

def primal(label):
 prob.set_val('beta',beta)
 t=time.monotonic();prob.run_model();comm.Barrier()
 cp=float(np.asarray(prob.get_val(name)).ravel()[0])
 status('PRIMAL_'+label,seconds=time.monotonic()-t,cp=cp)
 return cp

# Freeze the same initial flow state before any solution; all directional FD
# endpoints restore it instead of reusing the converged state.
initial_state=solver.DASolver.getStates().copy()
base=primal('BASELINE')
if comm.rank==0:
 try:
    txt=logtext();r=residuals(txt);cp=cp_trace(txt); fields=['Ux','Uy','Uz','p','nuTilda']
    assert all(len(r[f])==steps for f in fields)
    ratios={f:r[f][-1]/r[f][0] for f in fields}
    delta=abs(cp[-1]-cp[-500])/max(abs(cp[-500]),1e-6)
    gate=all(math.isfinite(x) and x<=1e-4 for x in ratios.values()) and delta<.005
    (case/'g1_gate.json').write_text(json.dumps({'primal_gate':gate,'ratios':ratios,'cp_change':delta,'cp':base,'terminal_residual':{f:r[f][-1] for f in fields},'steps':{f:len(r[f]) for f in fields}},indent=2)+'\n')
    (case/'g1_cp_trace.csv').write_text('iteration,roof_mean_cp\n'+''.join(f'{i},{x:.15g}\n' for i,x in enumerate(cp,1)))
    deep=all(math.isfinite(x) and x<=1e-6 for x in ratios.values())
    verdict=(gate,None,deep)
 except Exception as exc:verdict=(False,repr(exc),False);(case/'g1_gate_error.txt').write_text(repr(exc))
else:verdict=None
verdict=comm.bcast(verdict,root=0)
if verdict[1]:comm.Abort(88)
persist('g1_gate.json','g1_cp_trace.csv')
if arm=='D' and not verdict[2]:status('D_BASELINE_DEEP_GATE_FAILED');sys.exit(43)
if not verdict[0] or not verdict[2]:status('BASELINE_GATE_FAILED');sys.exit(41)
# Save one common converged state before every FD endpoint.
base_state=solver.DASolver.getStates().copy()
status('ADJOINT_START')
t=time.monotonic();totals=prob.compute_totals(of=[name],wrt=['beta']);comm.Barrier()
grad=np.asarray(next(iter(totals.values()))).ravel();assert len(grad)==n
status('ADJOINT_END',seconds=time.monotonic()-t)
if comm.rank==0:
    txt=logtext();true=[float(v) for v in re.findall(r'true resid norm\s+([0-9.eE+-]+)',txt,re.I)]
    check=json.loads((case/'c2a_true_residual.json').read_text())
    valid=len(true)>=2 and true[0]>0 and all(math.isfinite(x) and x>1e-290 for x in true)
    passed=valid and true[-1]/true[0]<1e-6 and math.isfinite(check['independent_Apsi_minus_b_over_b']) and check['independent_Apsi_minus_b_over_b']<1e-6 and int(check['ksp_reason'])>0
    check.update({'monitor_trace':true,'monitor_ratio':true[-1]/true[0] if valid else None,'adjoint_gate':passed})
    (case/'g1_adjoint_gate.json').write_text(json.dumps(check,indent=2)+'\n')
else:passed=None
passed=comm.bcast(passed,root=0)
persist('g1_adjoint_gate.json','c2a_true_residual.json')
if not passed:status('ADJOINT_GATE_FAILED');sys.exit(42)
if comm.rank==0:
    terminal=json.loads((case/'g1_gate.json').read_text())['terminal_residual']
else:terminal=None
terminal=comm.bcast(terminal,root=0)
# Reproduce the seeded global direction before doing the two new FD steps.
import hashlib
from numpy.random import default_rng
v=default_rng(2621).standard_normal(n)
digest=hashlib.sha256(np.asarray(grad,dtype=np.float64).tobytes()).hexdigest()
if len(set(comm.allgather(digest)))!=1:status('GRADIENT_RANK_MISMATCH');sys.exit(47)
chunk=np.array_split(np.arange(n),comm.size)[comm.rank]
dot=comm.allreduce(float(np.dot(grad[chunk],v[chunk])),op=MPI.SUM)
if comm.rank==0:
 (case/'c2a_direction_vectors.json').write_text(json.dumps({'seed':2621,'generator':'numpy.default_rng(2621).standard_normal(mesh_cells), global cell index order','n':n,'sha256':hashlib.sha256(v.tobytes()).hexdigest(),'adjoint_dot':dot,'objective':'roof-mean Cp','direction':'normal_seed2621'},indent=2)+'\n')
persist('c2a_direction_vectors.json')
status('GRADIENT_SAVED',adjoint_dot=dot)

# A cold endpoint always starts from the same state and fixed solver steps.
# No warm start across endpoints.
def cold_endpoint(label,target):
 solver.DASolver.setStates(initial_state.copy())
 solver._outputs[solver.stateName]=initial_state.copy()
 beta[:]=target
 before={f:len(v) for f,v in residuals(logtext()).items()} if comm.rank==0 else None
 cp=primal(label)
 if comm.rank==0:
  fresh={f:v[before[f]:] for f,v in residuals(logtext()).items() if f in terminal}
  ratios={f:(v[-1]/v[0] if v and v[0] else None) for f,v in fresh.items()}
  out={'label':label,'cp':cp,'steps':len(fresh.get('Ux',[])),
       'terminal_residual':{f:(v[-1] if v else None) for f,v in fresh.items()},
       'residual_ratio':ratios}
  out['valid']=out['steps']==steps and all(len(fresh.get(f,[]))==steps and ratios.get(f) is not None and ratios[f]<=1e-6 for f in terminal)
  with (case/'c2a_direction_endpoints.jsonl').open('a') as f:
   f.write(json.dumps(out)+'\n');f.flush();os.fsync(f.fileno())
 else:out=None
 persist('c2a_direction_endpoints.jsonl')
 out=comm.bcast(out,root=0);status('COLD_ENDPOINT',label=label,valid=out['valid'])
 return out

status('DIRECTIONS_START')
for label,direction,h in [('ones',np.ones(n),1e-3),*[('normal_seed2621',v,h) for h in (1e-3,3e-3,1e-2)],*[('ones',np.ones(n),h) for h in (3e-3,1e-2)]]:
 direction_dot=comm.allreduce(float(np.dot(grad[chunk],direction[chunk])),op=MPI.SUM)
 ends=[]
 for sign in (1,-1):
  target=1+sign*h*direction
  ends.append(cold_endpoint(f'DIR_{label}_{h}_{sign}',target))
 fd=(ends[0]['cp']-ends[1]['cp'])/(2*h)
 row={'kind':'direction','direction':label,'h':h,'adjoint_dot':direction_dot,'fd':fd,
      'valid':all(e['valid'] for e in ends),'relative_error':abs(direction_dot-fd)/abs(fd) if fd and all(e['valid'] for e in ends) else None,'endpoints':ends,'baseline_cp':base}
 if comm.rank==0:
  with (case/'c2a_direction_rows.jsonl').open('a') as f:
   f.write(json.dumps(row)+'\n');f.flush();os.fsync(f.fileno())
 persist('c2a_direction_rows.jsonl')
 status('DIRECTION_FD',direction=label,h=h)
status('COMPLETE')
