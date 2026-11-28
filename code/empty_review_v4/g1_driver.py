#!/usr/bin/env python3
"""G1 prereview driver: primal/adjoint and five-cell central differences.

Not executable until the R16.5 review and frozen cell IDs are present. A
successful process is NOT a G1 pass: assess roof-Cp trace and true residuals.
"""
import json,re,time,os
from pathlib import Path
import numpy as np
from mpi4py import MPI
from petsc4py import PETSc
import openmdao.api as om
from mphys.core import Multipoint
from mphys.scenarios import ScenarioAerodynamic
from dafoam.mphys import DAFoamBuilder
comm=MPI.COMM_WORLD
n=int(re.findall(r'\bcells:\s+(\d+)',Path('checkMesh.log').read_text())[-1])
selection=json.loads(Path('sample_cells.json').read_text())
ids=selection['cell_ids'];assert len(ids)==5 and len(set(ids))==5 and all(0<=i<n for i in ids)
# DALinearEqn.C calls KSPSetFromOptions: PETSc prints the unpreconditioned
# true residual on every iteration, independently from its custom history.
PETSc.Options().setValue('ksp_monitor_true_residual','')
opts={
 'solverName':'DASimpleFoam','primalMinResTol':1e-4,'primalMinResTolDiff':1e20,
 'primalBC':{'useWallFunction':True},
 'function':{'roofCp':{'type':'patchMean','source':'patchToFace','patches':['roof'],'varName':'p','varType':'scalar','index':0,'scale':1.0/50.0}},
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
prob=om.Problem(model=Top());prob.setup(mode='rev')
name='scenario1.aero_post.roofCp';beta=np.ones(n)
def primal(tag):
    prob.set_val('beta',beta)
    t=time.monotonic();prob.run_model();comm.Barrier()
    cp=float(np.asarray(prob.get_val(name)).ravel()[0]);dt=time.monotonic()-t
    if comm.rank==0:print('G1_PRIMAL',tag,'seconds',dt,'roofCp',cp,flush=True)
    return cp,dt
base,tbase=primal('baseline')
t=time.monotonic();totals=prob.compute_totals(of=[name],wrt=['beta']);comm.Barrier()
grad=np.asarray(next(iter(totals.values()))).ravel();assert len(grad)==n
if comm.rank==0:print('G1_ADJOINT_SECONDS',time.monotonic()-t,flush=True)
results=[];eps=1e-3
for i in ids:
    beta[i]=1+eps;plus,tp=primal(f'plus_{i}')
    beta[i]=1-eps;minus,tm=primal(f'minus_{i}')
    beta[i]=1
    fd=(plus-minus)/(2*eps)
    # Symmetric relative error, with a finite absolute denominator floor. If
    # both sensitivities are tiny, label undefined rather than fabricate 0%.
    scale=max(abs(fd),abs(float(grad[i])))
    rel=abs(fd-float(grad[i]))/scale if scale>=1e-12 else None
    results.append({'cell':i,'plus':plus,'minus':minus,'fd':fd,'adjoint':float(grad[i]),'relative_error':rel,'times':[tp,tm]})
    if comm.rank==0:print('G1_FD',json.dumps(results[-1]),flush=True)
if comm.rank==0:
    Path('g1_metrics.json').write_text(json.dumps({'source':'DAFoam v5.1.1 CRC G1','cells':n,'seed':selection['seed'],'baseline_cp':base,'baseline_seconds':tbase,'five':results},indent=2)+'\n')
