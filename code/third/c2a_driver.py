#!/usr/bin/env python3
"""C2a pre-registered SA adjoint/FD; fail closed on any missing evidence."""
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
assert n==168206 and ids==[51676,149479,154520,159137,159971]
ref=json.loads((case/'empty_reference.json').read_text()); u_ref=float(ref['U_at_H']); assert 0<u_ref<30
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

base=primal('BASELINE')
if comm.rank==0:
 try:
    txt=logtext();r=residuals(txt);cp=cp_trace(txt); fields=['Ux','Uy','Uz','p','nuTilda']
    assert all(len(r[f])>=5000 for f in fields)
    ratios={f:r[f][-1]/r[f][0] for f in fields}
    delta=abs(cp[-1]-cp[-500])/max(abs(cp[-500]),1e-6)
    gate=all(math.isfinite(x) and x<=1e-4 for x in ratios.values()) and delta<.005
    (case/'g1_gate.json').write_text(json.dumps({'primal_gate':gate,'ratios':ratios,'cp_change':delta,'cp':base,'terminal_residual':{f:r[f][-1] for f in fields},'steps':{f:len(r[f]) for f in fields}},indent=2)+'\n')
    (case/'g1_cp_trace.csv').write_text('iteration,roof_mean_cp\n'+''.join(f'{i},{x:.15g}\n' for i,x in enumerate(cp,1)))
    verdict=(gate,None)
 except Exception as exc:verdict=(False,repr(exc));(case/'g1_gate_error.txt').write_text(repr(exc))
else:verdict=None
verdict=comm.bcast(verdict,root=0)
if verdict[1]:comm.Abort(88)
if not verdict[0]:status('PRIMAL_GATE_FAILED');sys.exit(41)
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
if not passed:status('ADJOINT_GATE_FAILED');sys.exit(42)
if comm.rank==0:
    terminal=json.loads((case/'g1_gate.json').read_text())['terminal_residual']
else:terminal=None
terminal=comm.bcast(terminal,root=0)
# Diagnostic cells are selected after adjoint, never used in five-cell decision.
extra=sorted((i for i in range(n) if i not in ids),key=lambda i:abs(grad[i]),reverse=True)[:3]
if comm.rank==0:
    (case/'c2a_diagnostic_ids.json').write_text(json.dumps(extra)+'\n')
    (case/'c2a_gradient.json').write_text(json.dumps({'decision_ids':ids,'diagnostic_ids':extra,'decision':{str(i):float(grad[i]) for i in ids},'diagnostic':{str(i):float(grad[i]) for i in extra},'abs_min':float(np.min(np.abs(grad))),'abs_max':float(np.max(np.abs(grad))),'abs_mean':float(np.mean(np.abs(grad)))},indent=2)+'\n')
status('GRADIENT_SAVED')
# Use the first-run proven in-place FD path: retain the same problem and
# restore the same converged baseline state before each 5000-step endpoint.
# The unchanged solver has no dynamic early stop; verify the frozen terminal
# residual gate independently for each endpoint before accepting its Cp.
status('FD_SOLVER_READY',method='same_problem_no_rebuild',max_steps=5000)
results=[]
for eps,cellset in [(1e-3,ids),(1e-2,ids)]:
 for i in cellset:
    endpoints=[]
    for sign in (1,-1):
        solver.DASolver.setStates(base_state.copy())
        # Reset OpenMDAO's actual implicit-component output on every rank too.
        solver._outputs[solver.stateName]=base_state.copy()
        beta.fill(1);beta[i]=1+sign*eps
        before={f:len(v) for f,v in residuals(logtext()).items()} if comm.rank==0 else None
        value=primal(f'FD_{eps}_{i}_{sign}')
        if comm.rank==0:
            fresh={f:v[before[f]:] for f,v in residuals(logtext()).items() if f in terminal}
            ok=all(f in fresh and fresh[f] and fresh[f][-1]<=terminal[f]*10 for f in terminal)
            endpoint={'cell':i,'h':eps,'sign':sign,'cp':value,'step_count':len(fresh.get('Ux',[])),'residual':{f:(v[-1] if v else None) for f,v in fresh.items()},'deep_gate':ok}
        else:endpoint=None
        endpoint=comm.bcast(endpoint,root=0);endpoints.append(endpoint);status('FD_ENDPOINT',**endpoint)
        if not endpoint['deep_gate']:status('FD_NOISE_GATE_FAILED');sys.exit(43)
    fd=(endpoints[0]['cp']-endpoints[1]['cp'])/(2*eps)
    relative=abs(float(grad[i])-fd)/abs(fd) if fd!=0 else None
    row={'cell':i,'h':eps,'fd':fd,'adjoint':float(grad[i]),'relative_error':relative,'endpoints':endpoints,'diagnostic_only':i in extra}
    results.append(row)
    if comm.rank==0:
        with (case/'c2a_fd_rows.jsonl').open('a') as f:
            f.write(json.dumps(row)+'\n');f.flush();os.fsync(f.fileno())
    status('FD',cell=i,h=eps)
if comm.rank==0:(case/'g1_fd.json').write_text(json.dumps(results,indent=2)+'\n')
status('COMPLETE')
