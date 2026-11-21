#!/usr/bin/env python3
"""C2b SA medium directional derivatives (frozen Liang Hu-accepted gate)."""
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
n=sample['mesh_cells']; grade=os.environ['MESHCONV_GRADE']
assert grade in ('coarse','medium','fine') and n>100000
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

# Freeze the same initial flow state before any solution; all directional FD
# endpoints restore it instead of reusing the converged state.
initial_state=solver.DASolver.getStates().copy()
base=primal('BASELINE')
if comm.rank==0:
 try:
    txt=logtext();r=residuals(txt);cp=cp_trace(txt); fields=['Ux','Uy','Uz','p','nuTilda']
    assert all(len(r[f])==3000 for f in fields)
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
 np.save(case/'meshconv_gradient.npy',grad)
 (case/'meshconv_gradient_stats.json').write_text(json.dumps({'n':n,'min':float(grad.min()),'max':float(grad.max()),'norm':float(np.linalg.norm(grad))},indent=2)+'\n')
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
import hashlib
from physical_directions import read_centres
centres=read_centres(case/'0/C',n)
x,y,z=centres.T
v2=((x>=-16)&(x<=16)&(y>=-16)&(y<=16)&(z>=0)&(z<=16)).astype(float)
v3=((x>=8)&(x<=48)&(y>=-12)&(y<=12)&(z>=0)&(z<=12)).astype(float)
assert v2.sum()>0 and v3.sum()>0
digest=hashlib.sha256(np.asarray(grad,dtype=np.float64).tobytes()).hexdigest()
if len(set(comm.allgather(digest)))!=1:status('GRADIENT_RANK_MISMATCH');sys.exit(47)
chunk=np.array_split(np.arange(n),comm.size)[comm.rank]
vectors={'v1_all':np.ones(n),'v2_building_1H':v2,'v3_wake_5H':v3}
dot={key:comm.allreduce(float(np.dot(grad[chunk],vec[chunk])),op=MPI.SUM) for key,vec in vectors.items()}
if comm.rank==0:
 (case/'meshconv_directions.json').write_text(json.dumps({'n':n,'grade':grade,'boxes':{'v2':[-16,16,-16,16,0,16],'v3':[8,48,-12,12,0,12]},'directions':{k:{'count':int(np.count_nonzero(vec)),'sha256':hashlib.sha256(vec.tobytes()).hexdigest(),'adjoint_dot':dot[k]} for k,vec in vectors.items()},'centres_sha256':hashlib.sha256((case/'0/C').read_bytes()).hexdigest()},indent=2)+'\n')
status('GRADIENT_SAVED',adjoint_dot=dot)
if grade!='fine':sys.exit(0)

# A cold endpoint always starts from the same state and fixed 3000 solver steps.
# Cold 3000-step baseline and endpoints, C1 SA medium mesh rebuilt from same inputs.
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
  out['valid']=out['steps']==3000 and all(len(fresh.get(f,[]))==3000 and ratios.get(f) is not None and ratios[f]<=1e-6 for f in terminal)
  with (case/'c2a_direction_endpoints.jsonl').open('a') as f:
   f.write(json.dumps(out)+'\n');f.flush();os.fsync(f.fileno())
 else:out=None
 out=comm.bcast(out,root=0);status('COLD_ENDPOINT',label=label,valid=out['valid'])
 if not out['valid']:status('COLD_ENDPOINT_FAILED');sys.exit(45)
 return out

status('DIRECTIONS_START')
sequence=[('v1_all',1e-3),('v2_building_1H',1e-3),('v3_wake_5H',1e-3)]
for direction,h in sequence:
 v=vectors[direction]
 chunk=np.array_split(np.arange(n),comm.size)[comm.rank]
 dot=comm.allreduce(float(np.dot(grad[chunk],v[chunk])),op=MPI.SUM)
 ends=[]
 for sign in (1,-1):
  target=1+sign*h*v
  ends.append(cold_endpoint(f'DIR_{direction}_{h}_{sign}',target))
 fd=(ends[0]['cp']-ends[1]['cp'])/(2*h)
 row={'kind':'direction','direction':direction,'h':h,'adjoint_dot':dot,'fd':fd,
      'relative_error':abs(dot-fd)/abs(fd) if fd else None,'endpoints':ends,'baseline_cp':base}
 if comm.rank==0:
  with (case/'c2a_direction_rows.jsonl').open('a') as f:
   f.write(json.dumps(row)+'\n');f.flush();os.fsync(f.fileno())
 status('DIRECTION_FD',direction=direction,h=h)
status('COMPLETE')
