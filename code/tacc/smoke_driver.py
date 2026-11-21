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
n=sample['mesh_cells']
assert n==506198, n
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

assert comm.size==48,comm.size
prob.set_val('beta',beta)
prob.run_model()
comm.Barrier()
cp=float(np.asarray(prob.get_val(name)).ravel()[0])
assert math.isfinite(cp),cp
if comm.rank==0: print(f'SMOKE_PRIMAL_RETURNED ranks={comm.size} cp={cp:.16g}',flush=True)
