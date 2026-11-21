#!/usr/bin/env python3
"""C2a diagnostic cells only; original five-cell gate remains unchanged."""
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
assert n==int((case/"expected_cells").read_text()), ('mesh_cells',n)
u_ref=1.0 # Paper PDF p.1 H=1 m, U=1 m/s; Cp reference is the fixed uniform inlet
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
base=primal('BASELINE')
if comm.rank==0:
 try:
    txt=logtext();r=residuals(txt);cp=cp_trace(txt); fields=['Ux','Uy','Uz','p','nuTilda']
    assert all(len(r[f])==int((case/'expected_steps').read_text()) for f in fields)
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
status('PRIMAL_GATE_PASSED')
