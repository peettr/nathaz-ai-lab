#!/usr/bin/env python3
"""D0 roof area-mean Cp placeholder, SST betaFIOmega field sensitivity."""
import os
import re
import time
from pathlib import Path
import numpy as np
import openmdao.api as om
from mpi4py import MPI
from mphys.core import Multipoint
from mphys.scenarios import ScenarioAerodynamic
from dafoam.mphys import DAFoamBuilder

comm=MPI.COMM_WORLD
meshlog=Path('checkMesh.log').read_text()
n=int(re.findall(r'\bcells:\s+(\d+)', meshlog)[-1])
if comm.rank==0:
    print('D0_CELL_COUNT',n,flush=True)
# p is kinematic pressure. With Uref(8m)=10 m/s, q/rho=50 m2/s2.
opts={
 'solverName':'DASimpleFoam','primalMinResTol':1e-4,'primalMinResTolDiff':1e20,
 'primalBC':{'useWallFunction':True},
 'function':{'roofCp':{'type':'patchMean','source':'patchToFace','patches':['roof'], 'varName':'p','varType':'scalar','index':0,'scale':1.0/50.0}},
 'adjEqnOption':{'gmresRelTol':1e-6,'gmresMaxIters':2000,'gmresRestart':200,'pcFillLevel':1,'jacMatReOrdering':'rcm'},
 'normalizeStates':{'U':10.,'p':50.,'nut':0.1,'phi':1.,'k':0.5,'omega':5.},
 'inputInfo':{'beta':{'type':'field','fieldName':'betaFIOmega','fieldType':'scalar','distributed':False,'components':['solver','function']}},
}
class Top(Multipoint):
    def setup(self):
        builder=DAFoamBuilder(options=opts,mesh_options=None,scenario='aerodynamic')
        builder.initialize(self.comm)
        self.add_subsystem('dvs',om.IndepVarComp(),promotes=['*'])
        self.mphys_add_scenario('scenario1',ScenarioAerodynamic(aero_builder=builder))
    def configure(self):
        self.dvs.add_output('beta',val=np.ones(n),distributed=False)
        self.connect('beta','scenario1.beta')
        self.add_design_var('beta',lower=0.2,upper=5.)
        self.add_objective('scenario1.aero_post.roofCp')
prob=om.Problem(model=Top())
prob.setup(mode='rev')
t=time.monotonic(); prob.run_model(); comm.Barrier()
if comm.rank==0:print('D0_PRIMAL_SECONDS',time.monotonic()-t,flush=True)
t=time.monotonic(); totals=prob.compute_totals(of=['scenario1.aero_post.roofCp'],wrt=['beta']); comm.Barrier()
if comm.rank==0:
    print('D0_ADJOINT_SECONDS',time.monotonic()-t,flush=True)
    print('D0_DERIVATIVE_SHAPE', {k:np.shape(v) for k,v in totals.items()},flush=True)
